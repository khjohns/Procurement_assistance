import structlog
import asyncio
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
from models.procurement_models import TriageResult

logger = structlog.get_logger()


class SimpleSupabaseGateway:
    """
    Simplified Supabase Gateway that communicates directly via JSON-RPC
    instead of using the MCP ClientSession
    """
    
    def __init__(self, supabase_access_token: str, project_ref: str):
        self.supabase_access_token = supabase_access_token
        self.project_ref = project_ref
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._connected = False
        self._pending_requests = {}
        self._reader_task = None
        
    async def connect(self):
        """Start the MCP server and establish connection"""
        if self._connected:
            return
            
        logger.info("Starting Supabase MCP server process...")
        
        self.process = await asyncio.create_subprocess_exec(
            "npx", "-y", "@supabase/mcp-server-supabase@latest",
            "--project-ref", self.project_ref,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            env={
                "SUPABASE_ACCESS_TOKEN": self.supabase_access_token,
                **os.environ
            }
        )
        
        # Start reader task
        self._reader_task = asyncio.create_task(self._read_responses())
        
        # Wait a bit for server to start
        await asyncio.sleep(2)
        
        # Send initialize request
        logger.info("Sending initialize request...")
        result = await self._send_request("initialize", {
            "protocolVersion": "2025-06-18",  # Use the version the server expects
            "capabilities": {},
            "clientInfo": {
                "name": "supabase-gateway",
                "version": "1.0.0"
            }
        })
        
        logger.info("Server initialized", server_info=result.get("serverInfo"))
        
        # Send initialized notification
        await self._send_notification("notifications/initialized")
        
        # List available tools
        tools_result = await self._send_request("tools/list", {})
        available_tools = [tool["name"] for tool in tools_result.get("tools", [])]
        logger.info("Available tools", tools=available_tools)
        
        self._connected = True
        
    async def _read_responses(self):
        """Read responses from the server"""
        while self.process and self.process.returncode is None:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                    
                try:
                    response = json.loads(line.decode())
                    
                    # Handle response
                    if "id" in response and response["id"] in self._pending_requests:
                        future = self._pending_requests.pop(response["id"])
                        if "error" in response:
                            future.set_exception(Exception(response["error"]["message"]))
                        else:
                            future.set_result(response.get("result", {}))
                    
                except json.JSONDecodeError:
                    logger.error("Invalid JSON response", line=line.decode().strip())
                    
            except Exception as e:
                logger.error("Error reading response", error=str(e))
                break
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for response"""
        self._request_id += 1
        request_id = self._request_id
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }
        
        # Create a future for the response
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        # Send request
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str.encode())
        await self.process.stdin.drain()
        
        # Wait for response with timeout
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise Exception(f"Request timeout for {method}")
    
    async def _send_notification(self, method: str, params: Dict[str, Any] = None):
        """Send a JSON-RPC notification (no response expected)"""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        
        notification_str = json.dumps(notification) + "\n"
        self.process.stdin.write(notification_str.encode())
        await self.process.stdin.drain()
    
    async def execute_sql(self, query: str) -> Dict[str, Any]:
        """Execute SQL query via MCP"""
        if not self._connected:
            await self.connect()
            
        try:
            logger.info("Executing SQL", query=query[:100] + "..." if len(query) > 100 else query)
            
            result = await self._send_request("tools/call", {
                "name": "execute_sql",
                "arguments": {"query": query}
            })
            
            # Extract the actual content from the tool response
            if "content" in result and isinstance(result["content"], list):
                for item in result["content"]:
                    if item.get("type") == "text":
                        # Parse the JSON result from the text content
                        try:
                            data = json.loads(item["text"])
                            return {"success": True, "data": data}
                        except json.JSONDecodeError:
                            return {"success": True, "data": item["text"]}
            
            return {"success": True, "data": result}
            
        except Exception as e:
            logger.error("SQL execution failed", error=str(e))
            return {"success": False, "error": str(e)}
    
    def _escape_sql_value(self, value: Any) -> str:
        """Properly escape SQL values"""
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            escaped_value = value.replace("'", "''").replace("\\", "\\\\")
            return f"'{escaped_value}'"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, datetime):
            return f"'{value.isoformat()}'"
        else:
            escaped_value = str(value).replace("'", "''").replace("\\", "\\\\")
            return f"'{escaped_value}'"
    
    async def insert_data(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert data into a Supabase table"""
        if not data:
            return {"success": False, "error": "No data provided"}
            
        columns = list(data.keys())
        values = [self._escape_sql_value(value) for value in data.values()]
        
        columns_str = ", ".join(f'"{col}"' for col in columns)
        values_str = ", ".join(values)
        
        query = f'INSERT INTO "{table}" ({columns_str}) VALUES ({values_str}) RETURNING *;'
        
        return await self.execute_sql(query)
    
    async def ensure_table_exists(self):
        """Ensure the triage_results table exists"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS triage_results (
            id SERIAL PRIMARY KEY,
            request_id TEXT NOT NULL,
            farge TEXT NOT NULL,
            begrunnelse TEXT,
            confidence FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_triage_results_request_id 
        ON triage_results(request_id);
        """
        
        result = await self.execute_sql(create_table_sql)
        
        if result["success"]:
            logger.info("Triage results table ensured to exist")
        else:
            logger.error("Failed to create triage results table", error=result["error"])
            raise Exception(f"Table creation failed: {result['error']}")
    
    async def lagre_resultat(self, request_id: str, triage_result: TriageResult):
        """Save triage result to Supabase"""
        logger.info("Saving triage result",
                    request_id=request_id,
                    farge=triage_result.farge)
        
        data_to_insert = {
            "request_id": request_id,
            "farge": triage_result.farge,
            "begrunnelse": triage_result.begrunnelse,
            "confidence": triage_result.confidence,
            "created_at": datetime.utcnow()
        }
        
        try:
            result = await self.insert_data("triage_results", data_to_insert)
            
            if result["success"]:
                logger.info("Triage result saved", request_id=request_id)
                return result
            else:
                logger.error("Failed to save triage result", error=result["error"])
                raise Exception(f"Database insert failed: {result['error']}")
                
        except Exception as e:
            logger.error("Exception while saving triage result", error=str(e))
            raise
    
    async def close(self):
        """Close the gateway and cleanup"""
        self._connected = False
        
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        
        if self.process:
            self.process.terminate()
            await self.process.wait()
        
        logger.info("SimpleSupabaseGateway closed")


class SimpleSupabaseGatewayManager:
    """Context manager for SimpleSupabaseGateway"""
    
    def __init__(self, supabase_access_token: str, project_ref: str):
        self.gateway = SimpleSupabaseGateway(supabase_access_token, project_ref)
    
    async def __aenter__(self):
        await self.gateway.connect()
        await self.gateway.ensure_table_exists()
        return self.gateway
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.gateway.close()


# Test function
async def test_simple_gateway():
    """Test the simplified gateway"""
    access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    
    if not access_token or not project_ref:
        raise ValueError("SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF must be set")
    
    async with SimpleSupabaseGatewayManager(access_token, project_ref) as gateway:
        # Test SQL execution
        result = await gateway.execute_sql("SELECT current_timestamp;")
        print(f"Current timestamp: {result}")
        
        # Test triage result insertion
        triage_result = TriageResult(
            farge="grønn",
            begrunnelse="Test fra simplified gateway",
            confidence=0.95
        )
        
        await gateway.lagre_resultat("test-simple-123", triage_result)
        print("Triage result saved successfully!")


if __name__ == "__main__":
    asyncio.run(test_simple_gateway())