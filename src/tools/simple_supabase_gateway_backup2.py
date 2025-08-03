import asyncio
import os
import json
import re
import structlog
from typing import Dict, Any, Optional, List
from datetime import datetime

from models.procurement_models import TriageResult
from mcp_library.mcp_client import MCPServerLauncher, SupabaseMCPWrapper, MCPClient

logger = structlog.get_logger()

class SupabaseGateway:
    """A gateway to interact with Supabase via an MCP client."""
    def __init__(self, client: MCPClient):
        self.mcp_client = client
        self.sql = SupabaseMCPWrapper(client)

    def _escape_sql_value(self, value: Any) -> str:
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            # Escape single quotes for SQL
            return f"'{value.replace("'", "''")}'"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, datetime):
            return f"'{value.isoformat()}'"
        elif isinstance(value, list):
            # pgvector expects a string representation of the list '[1,2,3]'
            return f"'{str(value)}'"
        elif isinstance(value, dict):
            # Escape single quotes in the JSON string
            json_str = json.dumps(value)
            return f"'{json_str.replace("'", "''")}'"
        else:
            return f"'{str(value)}'"

    def _parse_untrusted_data(self, response_str: str) -> Optional[Any]:
        """Parses the JSON content from the untrusted data block more robustly."""
        # This regex looks for a JSON array '[...]' inside the response string.
        match = re.search(r'(\[.*\])', response_str, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse JSON from untrusted data", json_str=json_str, error=str(e))
                return None
        logger.warning("Could not find valid JSON array in untrusted data block", response_str=response_str)
        return None

    async def create_document_record(self, navn: str, type: str) -> str:
        """Oppretter en ny rad i oslomodell_dokumenter og returnerer ID-en."""
        logger.info("Creating document record in Supabase", doc_name=navn)
        data = {"dokument_navn": navn, "dokument_type": type}
        columns = ", ".join(data.keys())
        values = ", ".join(self._escape_sql_value(v) for v in data.values())
        query = f"INSERT INTO public.oslomodell_dokumenter ({columns}) VALUES ({values}) RETURNING dokument_id;"

        try:
            result_str = await self.sql.execute_sql(query)
            logger.info("Document record raw response", db_response=result_str)
            result = self._parse_untrusted_data(result_str)
            
            if result and isinstance(result, list) and len(result) > 0 and result[0].get('dokument_id'):
                return result[0]['dokument_id']
            else:
                logger.error("Failed to retrieve document_id from parsed DB response", parsed_response=result)
                raise ValueError("Could not create document record.")
        except Exception as e:
            logger.error("Failed to create document record", error=str(e), exc_info=True)
            raise

    async def store_chunk(self, dokument_id: str, innhold: str, metadata: Dict, embedding: List[float], chunk_nummer: int):
        """Lagrer en chunk i oslomodell_chunks-tabellen."""
        logger.info("Storing chunk in Supabase", chunk_num=chunk_nummer)
        data = {
            "dokument_id": dokument_id,
            "innhold": innhold,
            "metadata": metadata,
            "embedding": embedding,
            "chunk_nummer": chunk_nummer,
        }
        columns = ", ".join(data.keys())
        values = ", ".join(self._escape_sql_value(v) for v in data.values())
        query = f"INSERT INTO public.oslomodell_chunks ({columns}) VALUES ({values}) RETURNING chunk_id;"

        try:
            result = await self.sql.execute_sql(query)
            logger.info("Chunk stored successfully", db_response=result)
            return result
        except Exception as e:
            logger.error("Failed to store chunk", error=str(e), exc_info=True)
            raise

    async def lagre_resultat(self, request_id: str, triage_result: TriageResult):
        logger.info("Saving triage result to Supabase via RPC", request_id=request_id)
        
        query = f"SELECT lagre_triage_resultat(" \
                f"{self._escape_sql_value(request_id)}, " \
                f"{self._escape_sql_value(triage_result.farge)}, " \
                f"{self._escape_sql_value(triage_result.begrunnelse)}, " \
                f"{self._escape_sql_value(triage_result.confidence)})::jsonb;"
        
        try:
            result_str = await self.sql.execute_sql(query)
            logger.info("Triage result RPC raw response", db_response=result_str)
            
            # Parse the JSONB result from the RPC function
            result = self._parse_untrusted_data(result_str)
            
            if result and isinstance(result, list) and len(result) > 0 and result[0].get('lagre_triage_resultat'):
                rpc_response = result[0]['lagre_triage_resultat']
                logger.info("Triage result saved successfully via RPC", rpc_response=rpc_response)
                return rpc_response
            else:
                logger.error("Failed to retrieve RPC response for triage result", parsed_response=result)
                raise ValueError("Could not save triage result via RPC.")
        except Exception as e:
            logger.error("Failed to save triage result via RPC", error=str(e), exc_info=True)
            raise

    async def sett_status(self, request_id: str, status: str):
        logger.info("Updating status in Supabase via RPC", request_id=request_id, status=status)
        
        query = f"SELECT sett_status(" \
                f"{self._escape_sql_value(request_id)}, " \
                f"{self._escape_sql_value(status)})::jsonb;"
        
        try:
            result_str = await self.sql.execute_sql(query)
            logger.info("Status RPC raw response", db_response=result_str)
            
            # Parse the JSONB result from the RPC function
            result = self._parse_untrusted_data(result_str)
            
            if result and isinstance(result, list) and len(result) > 0 and result[0].get('sett_status'):
                rpc_response = result[0]['sett_status']
                logger.info("Status updated successfully via RPC", rpc_response=rpc_response)
                return rpc_response
            else:
                logger.error("Failed to retrieve RPC response for status update", parsed_response=result)
                raise ValueError("Could not update status via RPC.")
        except Exception as e:
            logger.error("Failed to update status via RPC", error=str(e), exc_info=True)
            raise

class SupabaseGatewayManager:
    """Context manager to handle the lifecycle of the Supabase MCP client."""
    def __init__(self):
        self.project_ref = os.getenv("SUPABASE_PROJECT_REF")
        self.access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
        self.client: Optional[MCPClient] = None

    async def __aenter__(self) -> SupabaseGateway:
        if not self.project_ref or not self.access_token:
            logger.error("Supabase project_ref or access_token not set in .env file")
            raise ValueError("Supabase configuration missing.")
        
        self.client = await MCPServerLauncher.launch_supabase(
            project_ref=self.project_ref,
            access_token=self.access_token
        )
        return SupabaseGateway(self.client)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.stop()
            logger.info("Supabase MCP client stopped.")