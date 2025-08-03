import structlog
import asyncio
import os
import json
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from datetime import datetime

# MCP Client imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.models.procurement_models import TriageResult

logger = structlog.get_logger()

class SupabaseGateway:
    def __init__(self, read_stream, write_stream):
        """
        Initialize Supabase Gateway with pre-established MCP streams.
        Note: streams can be either asyncio.StreamReader/Writer or MemoryObjectReceiveStream/SendStream
        """
        self.read_stream = read_stream
        self.write_stream = write_stream
        self.session: Optional[ClientSession] = None
        self.logger = logger
        self._connected = False
        self._initialization_lock = asyncio.Lock()
        
        logger.info("SupabaseGateway initialized with streams",
                   read_stream_type=type(read_stream).__name__,
                   write_stream_type=type(write_stream).__name__)
    
    async def _test_stream_communication(self):
        """Test basic stream communication before initializing session"""
        try:
            logger.info("Testing stream communication...")
            
            # For subprocess streams (StreamReader/StreamWriter), we need different checks
            if self.read_stream is None:
                raise Exception("Read stream is None")
            
            if self.write_stream is None:
                raise Exception("Write stream is None")
            
            # Check stream types
            read_stream_type = type(self.read_stream).__name__
            write_stream_type = type(self.write_stream).__name__
            
            logger.info("Stream types verified", 
                       read_stream_type=read_stream_type,
                       write_stream_type=write_stream_type)
            
            # For subprocess streams, check if they're actually asyncio.StreamReader/Writer
            if hasattr(self.read_stream, 'at_eof'):
                # This is a real StreamReader
                if self.read_stream.at_eof():
                    raise Exception("Read stream is at EOF - connection may be closed")
            
            logger.info("Stream communication test passed")
            return True
            
        except Exception as e:
            logger.error("Stream communication test failed", error=str(e))
            return False

    async def initialize_session(self):
        """
        Initializes the MCP client session with enhanced debugging.
        """
        async with self._initialization_lock:
            if self._connected:
                return
                
            try:
                # Test stream communication first
                if not await self._test_stream_communication():
                    raise Exception("Stream communication test failed")
                
                logger.info("Creating MCP ClientSession")
                self.session = ClientSession(self.read_stream, self.write_stream)
                
                logger.info("Starting MCP ClientSession initialization...")
                
                # Add timeout and detailed logging for each step
                start_time = asyncio.get_event_loop().time()
                
                # Step 1: Initialize session with timeout
                init_start = asyncio.get_event_loop().time()
                await asyncio.wait_for(self.session.initialize(), timeout=30.0)  # Increased timeout
                init_duration = asyncio.get_event_loop().time() - init_start
                logger.info("MCP ClientSession.initialize() completed", duration=f"{init_duration:.2f}s")
                
                # Step 2: Test basic connectivity
                logger.info("Testing basic MCP connectivity...")
                try:
                    # Try to get server info first (simpler than listing tools)
                    logger.info("Attempting to get server capabilities...")
                    
                    # List tools with timeout
                    tools_start = asyncio.get_event_loop().time()
                    tools_response = await asyncio.wait_for(
                        self.session.list_tools(), 
                        timeout=30.0  # Increased timeout
                    )
                    tools_duration = asyncio.get_event_loop().time() - tools_start
                    
                    available_tools = [tool.name for tool in tools_response.tools]
                    logger.info("Tools listed successfully", 
                              duration=f"{tools_duration:.2f}s",
                              tool_count=len(available_tools),
                              available_tools=available_tools)
                    
                except asyncio.TimeoutError:
                    logger.error("Timeout while listing tools - server may not be responding")
                    raise Exception("Server is not responding to tool list request")
                except Exception as e:
                    logger.error("Failed to list tools", error=str(e), error_type=type(e).__name__)
                    raise Exception(f"Tool listing failed: {str(e)}")
                
                total_duration = asyncio.get_event_loop().time() - start_time
                self._connected = True
                logger.info("Supabase MCP session initialized successfully", 
                          total_duration=f"{total_duration:.2f}s",
                          available_tools=available_tools)
                
            except asyncio.TimeoutError as e:
                logger.error("Timeout during MCP session initialization", 
                           timeout_stage="session_initialize_or_list_tools")
                self._connected = False
                self.session = None
                raise Exception("MCP session initialization timed out")
                
            except Exception as e:
                logger.error("Failed to initialize MCP session", 
                           error=str(e), 
                           error_type=type(e).__name__)
                self._connected = False
                self.session = None
                raise

    async def _ensure_connected(self):
        """
        Ensure MCP session is established.
        """
        if not self._connected:
            await self.initialize_session()

    async def close(self):
        """
        Clean close of the gateway
        """
        self._connected = False
        # Note: ClientSession doesn't have a close method, just mark as disconnected
        self.session = None
        logger.info("SupabaseGateway closed")

    async def execute_sql(self, query: str) -> Dict[str, Any]:
        """
        Execute SQL query via Supabase MCP
        """
        await self._ensure_connected()
        
        try:
            logger.info("Executing SQL via MCP", query=query[:100] + "..." if len(query) > 100 else query)
            
            result = await self.session.call_tool(
                "execute_sql",
                arguments={"query": query}
            )
            
            logger.info("SQL executed successfully via MCP")
            return {"success": True, "data": result.content}
            
        except Exception as e:
            logger.error("SQL execution failed via MCP", error=str(e), query=query[:100])
            return {"success": False, "error": str(e)}

    def _escape_sql_value(self, value: Any) -> str:
        """
        Properly escape SQL values
        """
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            # Proper SQL string escaping
            escaped_value = value.replace("'", "''").replace("\\", "\\\\")
            return f"'{escaped_value}'"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, datetime):
            return f"'{value.isoformat()}'"
        else:
            # For other types, convert to string and escape
            escaped_value = str(value).replace("'", "''").replace("\\", "\\\\")
            return f"'{escaped_value}'"

    async def insert_data(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert data into a Supabase table using SQL
        """
        if not data:
            return {"success": False, "error": "No data provided"}

        columns = list(data.keys())
        values = [self._escape_sql_value(value) for value in data.values()]
        
        columns_str = ", ".join(f'"{col}"' for col in columns)  # Quote column names
        values_str = ", ".join(values)
        
        query = f'INSERT INTO "{table}" ({columns_str}) VALUES ({values_str}) RETURNING *;'
        
        logger.info("Inserting data via MCP", table=table, columns=columns)
        return await self.execute_sql(query)

    async def update_data(self, table: str, data: Dict[str, Any], where_clause: str) -> Dict[str, Any]:
        """
        Update data in a Supabase table
        """
        if not data:
            return {"success": False, "error": "No data provided"}

        if not where_clause:
            return {"success": False, "error": "WHERE clause is required for updates"}

        set_clauses = []
        for column, value in data.items():
            escaped_value = self._escape_sql_value(value)
            set_clauses.append(f'"{column}" = {escaped_value}')
        
        set_clause = ", ".join(set_clauses)
        query = f'UPDATE "{table}" SET {set_clause} WHERE {where_clause} RETURNING *;'
        
        logger.info("Updating data via MCP", table=table, where=where_clause)
        return await self.execute_sql(query)

    async def select_data(self, table: str, columns: str = "*", where_clause: str = None, 
                         order_by: str = None, limit: int = None) -> Dict[str, Any]:
        """
        Select data from a Supabase table
        """
        query = f'SELECT {columns} FROM "{table}"'
        
        if where_clause:
            query += f" WHERE {where_clause}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
            
        if limit:
            query += f" LIMIT {limit}"
        
        query += ";"
        
        logger.info("Selecting data via MCP", table=table, where=where_clause)
        return await self.execute_sql(query)

    async def lagre_resultat(self, request_id: str, triage_result: TriageResult):
        """
        Lagre triageresultat til Supabase via MCP
        """
        logger.info("Attempting to save triage result to Supabase via MCP",
                    request_id=request_id,
                    farge=triage_result.farge,
                    begrunnelse=triage_result.begrunnelse,
                    confidence=triage_result.confidence)
        
        # Use current timestamp instead of NOW() function
        data_to_insert = {
            "request_id": request_id,
            "farge": triage_result.farge,
            "begrunnelse": triage_result.begrunnelse,
            "confidence": triage_result.confidence,
            "created_at": datetime.utcnow()  # Use Python datetime
        }
        
        try:
            result = await self.insert_data("triage_results", data_to_insert)
            
            if result["success"]:
                logger.info("Triage result saved to Supabase via MCP", 
                           request_id=request_id, result=result["data"])
                return result
            else:
                logger.error("Failed to save triage result to Supabase via MCP", 
                           error=result["error"], request_id=request_id)
                raise Exception(f"Database insert failed: {result['error']}")
                
        except Exception as e:
            logger.error("Exception while saving triage result to Supabase via MCP", 
                        error=str(e), request_id=request_id)
            raise

    async def get_triage_results(self, request_id: str = None, limit: int = 100) -> Dict[str, Any]:
        """
        Hent triageresultater fra Supabase
        """
        where_clause = f"request_id = '{request_id}'" if request_id else None
        
        return await self.select_data(
            table="triage_results",
            where_clause=where_clause,
            order_by="created_at DESC",
            limit=limit
        )

    async def ensure_table_exists(self):
        """
        Ensure the triage_results table exists, create if it doesn't
        """
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
        
        CREATE INDEX IF NOT EXISTS idx_triage_results_created_at 
        ON triage_results(created_at);
        """
        
        result = await self.execute_sql(create_table_sql)
        
        if result["success"]:
            logger.info("Triage results table ensured to exist")
        else:
            logger.error("Failed to create triage results table", error=result["error"])
            raise Exception(f"Table creation failed: {result['error']}")


class SupabaseGatewayManager:
    """Context manager for SupabaseGateway with automatic connection handling"""
    
    def __init__(self, supabase_access_token: str, project_ref: str, timeout: float = 60.0):
        self.supabase_access_token = supabase_access_token
        self.project_ref = project_ref
        self.timeout = timeout
        self.gateway: Optional[SupabaseGateway] = None
        self.transport_cm: Optional[asynccontextmanager] = None
        self.read_stream: Optional[asyncio.StreamReader] = None
        self.write_stream: Optional[asyncio.StreamWriter] = None

    async def _test_server_executable(self):
        """Test if the MCP server can be executed"""
        try:
            logger.info("Testing MCP server executable availability...")
            
            # Test if npx and the package are available
            proc = await asyncio.create_subprocess_exec(
                "npx", "-y", "@supabase/mcp-server-supabase@latest", "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    "SUPABASE_ACCESS_TOKEN": self.supabase_access_token,
                    **os.environ
                }
            )
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            
            if proc.returncode == 0:
                logger.info("MCP server executable test passed")
                return True
            else:
                logger.error("MCP server executable test failed", 
                           returncode=proc.returncode,
                           stderr=stderr.decode() if stderr else "")
                return False
                
        except asyncio.TimeoutError:
            logger.error("MCP server executable test timed out")
            return False
        except Exception as e:
            logger.error("MCP server executable test failed", error=str(e))
            return False

    async def __aenter__(self):
        # Test server executable first
        if not await self._test_server_executable():
            raise Exception("MCP server executable test failed")
        
        server_params = StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@supabase/mcp-server-supabase@latest",
                "--project-ref", self.project_ref
            ],
            env={
                "SUPABASE_ACCESS_TOKEN": self.supabase_access_token,
                **os.environ
            }
        )
        
        logger.info("Starting Supabase MCP server process", 
                   project_ref=self.project_ref[:8] + "..." if len(self.project_ref) > 8 else self.project_ref,
                   command=" ".join([server_params.command] + server_params.args))
        
        try:
            # Get the transport context manager
            self.transport_cm = stdio_client(server_params)
            
            # Enter the transport context
            logger.info("Establishing transport connection...")
            connection_start = asyncio.get_event_loop().time()
            
            # Use the context manager properly
            transport_result = await self.transport_cm.__aenter__()
            self.read_stream, self.write_stream = transport_result
            
            connection_duration = asyncio.get_event_loop().time() - connection_start
            logger.info("Transport streams established successfully", 
                      duration=f"{connection_duration:.2f}s",
                      read_stream_type=type(self.read_stream).__name__,
                      write_stream_type=type(self.write_stream).__name__)
            
            # Create gateway
            self.gateway = SupabaseGateway(self.read_stream, self.write_stream)
            
            # Give the process more time to fully start
            logger.info("Waiting for server process to fully initialize...")
            await asyncio.sleep(20.0)  # Increased wait time even more
            
            # Initialize session with retry logic
            await self._initialize_with_retry()
            
            # Ensure table exists after successful connection
            logger.info("Ensuring database table exists...")
            await self.gateway.ensure_table_exists()
            
            logger.info("Supabase MCP connection fully established and ready")
            return self.gateway
            
        except Exception as e:
            logger.error("Failed to initialize Supabase MCP connection", 
                        error=str(e), 
                        error_type=type(e).__name__)
            # Clean up on failure
            await self._cleanup()
            raise

    async def _initialize_with_retry(self, max_retries: int = 3, initial_delay: float = 5.0):
        """
        Initialize the MCP session with retry logic and exponential backoff
        """
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to initialize MCP session (attempt {attempt + 1}/{max_retries})")
                
                # Wrap initialization in timeout with longer timeout
                init_task = asyncio.create_task(self.gateway.initialize_session())
                await asyncio.wait_for(init_task, timeout=40.0)  # Further increased timeout
                
                logger.info("MCP session initialized successfully")
                return
                
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(f"Session initialization timeout on attempt {attempt + 1}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Session initialization failed on attempt {attempt + 1}", 
                             error=str(e), 
                             error_type=type(e).__name__)
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {delay:.1f} seconds...")
                await asyncio.sleep(delay)
                delay *= 1.5
        
        raise Exception(f"Failed to initialize MCP session after {max_retries} attempts: {last_exception}")

    async def _cleanup(self):
        """
        Clean up resources with proper error handling
        """
        cleanup_tasks = []
        
        # Close gateway
        if self.gateway:
            cleanup_tasks.append(self._safe_close_gateway())
        
        # Close transport
        if self.transport_cm:
            cleanup_tasks.append(self._safe_close_transport())
        
        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Cleanup timed out, some resources may not be properly closed")

    async def _safe_close_gateway(self):
        """Safely close the gateway"""
        try:
            await asyncio.wait_for(self.gateway.close(), timeout=5.0)
        except Exception as e:
            logger.warning("Error closing gateway", error=str(e))

    async def _safe_close_transport(self):
        """Safely close the transport"""
        try:
            await asyncio.wait_for(
                self.transport_cm.__aexit__(None, None, None), 
                timeout=5.0
            )
        except Exception as e:
            logger.warning("Error closing transport", error=str(e))

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()
        logger.info("Disconnected from Supabase MCP")


# Test function
async def test_gateway():
    """Test the gateway functionality"""
    access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    
    if not access_token or not project_ref:
        raise ValueError("SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF must be set")
    
    async with SupabaseGatewayManager(access_token, project_ref) as gateway:
        # Test table listing
        tables_result = await gateway.select_data(
            "information_schema.tables", 
            "table_name", 
            "table_schema = 'public'"
        )
        print(f"Tables: {tables_result}")
        
        # Test triage result insertion
        triage_result = TriageResult(
            farge="grønn",
            begrunnelse="Standard IT-anskaffelse under terskelverdi",
            confidence=0.85
        )
        
        await gateway.lagre_resultat("test-request-123", triage_result)
        
        # Test retrieval
        results = await gateway.get_triage_results("test-request-123")
        print(f"Retrieved results: {results}")


if __name__ == "__main__":
    asyncio.run(test_gateway())