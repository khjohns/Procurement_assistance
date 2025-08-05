# gateway/main.py - Refaktorert til engelsk API i henhold til refaktoreringsguide
import uvicorn
import asyncpg
import asyncio
import os
import structlog
import uuid
from fastapi import FastAPI, Request, HTTPException
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import json
import httpx

# --- Configuration ---
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in the environment variables.")

logger = structlog.get_logger()

# --- Pydantic Models ---
class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = {}
    id: Optional[int] = None

class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[int] = None

class HealthStatus(BaseModel):
    status: str
    database: str
    timestamp: str
    version: str = "2.0"

# --- Error Handling ---
class RPCError(Exception):
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

class ErrorCodes:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Custom error codes
    UNAUTHORIZED = -32001
    SERVICE_UNAVAILABLE = -32002
    RATE_LIMITED = -32003
    TIMEOUT_ERROR = -32004

# --- Rate Limiting ---
class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.agent_requests = defaultdict(list)
        # Differentiated limits based on agent type
        self.limits = {
            "reasoning_orchestrator": 120,  # Higher limit for orchestrator
            "triage_agent": 60,             # Standard for specialists
            "oslomodell_agent": 30,         # Lower for RAG-heavy operations
            "default": 60
        }
    
    async def check_rate_limit(self, agent_id: str) -> bool:
        limit = self.limits.get(agent_id, self.limits["default"])
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Remove old requests
        self.agent_requests[agent_id] = [
            req_time for req_time in self.agent_requests[agent_id]
            if req_time > minute_ago
        ]
        
        current_count = len(self.agent_requests[agent_id])
        
        if current_count >= limit:
            logger.warning("Rate limit exceeded", 
                         agent_id=agent_id, 
                         current_requests=current_count, 
                         limit=limit)
            return False
        
        self.agent_requests[agent_id].append(now)
        return True

# --- Enhanced Response Validation ---
class ResponseValidator:
    """Validates RPC responses based on method with business logic."""
    
    @staticmethod
    async def validate(result: Any, method: str) -> Any:
        """Validates that RPC response is in expected format"""
        validators = {
            "database.save_triage_result": ResponseValidator._validate_triage_save,
            "database.search_oslomodell_requirements": ResponseValidator._validate_search_result,
            "database.set_procurement_status": ResponseValidator._validate_status_update,
            "database.save_protocol": ResponseValidator._validate_protocol_save,
            "database.create_procurement": ResponseValidator._validate_procurement_creation
        }
        
        validator = validators.get(method)
        if validator:
            return await validator(result)
        return result
    
    @staticmethod
    async def _validate_triage_save(result: Any) -> Dict[str, Any]:
        """Validates response from save_triage_result"""
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Invalid JSON response from database")
        
        if not isinstance(result, dict):
            raise RPCError(ErrorCodes.INTERNAL_ERROR, "Expected dict response")
        
        required_fields = ["status", "resultId"]
        for field in required_fields:
            if field not in result:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, f"Missing required field: {field}")
        
        return result
    
    @staticmethod
    async def _validate_procurement_creation(result: Any) -> Dict[str, Any]:
        """Validates response from create_procurement"""
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Invalid JSON response from database")
        
        if not isinstance(result, dict):
            raise RPCError(ErrorCodes.INTERNAL_ERROR, "Expected dict response")
        
        if result.get("status") == "success":
            if "procurementId" not in result:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Missing procurementId in successful response")
            
            # Validate UUID format
            try:
                uuid.UUID(str(result["procurementId"]))
            except ValueError:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Invalid UUID format for procurementId")
        
        return result
    
    @staticmethod
    async def _validate_search_result(result: Any) -> List[Dict[str, Any]]:
        """Validates response from search functions"""
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Invalid JSON response from database")
        
        if not isinstance(result, list):
            raise RPCError(ErrorCodes.INTERNAL_ERROR, "Expected list response")
        
        return result
    
    @staticmethod
    async def _validate_status_update(result: Any) -> Dict[str, Any]:
        """Validates response from status update"""
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Invalid JSON response from database")
        
        return result
    
    @staticmethod
    async def _validate_protocol_save(result: Any) -> Dict[str, Any]:
        """Validates response from save_protocol"""
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Invalid JSON response from database")
        
        if result.get("status") == "success":
            if "protocolId" not in result:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Missing protocolId in successful response")
        
        return result

# --- Input Security Validation ---
class SecurityValidator:
    """Enhanced security validation for procurement data."""
    
    @staticmethod
    async def validate_procurement_input(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize procurement input parameters."""
        
        # Business logic validation
        value = params.get("value", 0)
        if value < 0:
            logger.warning("Negative procurement value rejected", value=value)
            raise RPCError(ErrorCodes.INVALID_PARAMS, "Procurement value cannot be negative")
        
        if value > 100_000_000:  # 100M NOK - suspiciously high
            logger.warning("Suspiciously high value flagged", value=value)
            # Don't block, but flag for manual review
        
        # Security sanitization
        description = params.get("description", "")
        
        # Prevent DoS attacks
        if len(description) > 50000:
            logger.warning("Description too long, truncating", original_length=len(description))
            params["description"] = description[:50000]
        
        # Prevent injection of malicious content
        dangerous_patterns = ["<script>", "javascript:", "data:", "<?php", "<%"]
        for pattern in dangerous_patterns:
            if pattern in description.lower():
                logger.error("Potentially malicious content detected", pattern=pattern)
                raise RPCError(ErrorCodes.INVALID_PARAMS, f"Prohibited content detected: {pattern}")
        
        # Consistency check
        name = params.get("name", "").strip()
        if not name or len(name) < 3:
            raise RPCError(ErrorCodes.INVALID_PARAMS, "Procurement name must be at least 3 characters")
        
        return params

# --- Database and App State ---
class AppState:
    db_pool: Optional[asyncpg.Pool] = None
    service_catalog: Dict[str, Any] = {}
    acl_config: Dict[str, Any] = {}
    rate_limiter: RateLimiter = RateLimiter()
    response_validator: ResponseValidator = ResponseValidator()
    security_validator: SecurityValidator = SecurityValidator()

app_state = AppState()

# --- Service Catalog Management (Updated to English methods) ---
async def load_service_catalog(pool: asyncpg.Pool) -> Dict[str, Any]:
    """Loads service catalog from database with English method names."""
    try:
        async with pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'gateway_service_catalog'
                );
            """)
            
            if not table_exists:
                logger.info("Service catalog table not found, using default configuration")
                return get_default_service_catalog()
            
            # Check if function_metadata column exists
            metadata_column_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'gateway_service_catalog' 
                    AND column_name = 'function_metadata'
                );
            """)
            
            if metadata_column_exists:
                # New structure with metadata
                rows = await conn.fetch("""
                    SELECT service_name, service_type, function_key, 
                           sql_function_name, function_metadata
                    FROM gateway_service_catalog
                    WHERE is_active = true
                """)
            else:
                # Old structure without metadata
                rows = await conn.fetch("""
                    SELECT service_name, service_type, function_key, sql_function_name
                    FROM gateway_service_catalog
                    WHERE is_active = true
                """)
            
            catalog = {}
            for row in rows:
                service_name = row['service_name']
                if service_name not in catalog:
                    catalog[service_name] = {
                        "type": row['service_type'],
                        "functions": {}
                    }
                
                # Handle metadata that can be string or JSONB
                metadata = {}
                if metadata_column_exists and row.get('function_metadata'):
                    raw_metadata = row['function_metadata']
                    
                    # If metadata is a string, parse it as JSON
                    if isinstance(raw_metadata, str):
                        try:
                            metadata = json.loads(raw_metadata)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in metadata for {service_name}.{row['function_key']}")
                            metadata = {}
                    # If metadata is already dict/JSONB
                    elif isinstance(raw_metadata, dict):
                        metadata = raw_metadata
                    else:
                        logger.warning(f"Unexpected metadata type for {service_name}.{row['function_key']}: {type(raw_metadata)}")
                
                # Always store as dictionary structure
                catalog[service_name]["functions"][row['function_key']] = {
                    "sql_function_name": row['sql_function_name'],
                    "metadata": metadata
                }
            
            return catalog
    except Exception as e:
        logger.error("Failed to load service catalog", error=str(e))
        return get_default_service_catalog()

def get_default_service_catalog():
    """Returns default service catalog with English method names."""
    return {
        "database": {
            "type": "postgres_rpc",
            "functions": {
                "create_procurement": {
                    "sql_function_name": "create_procurement",
                    "metadata": {
                        "description": "Creates a new procurement case",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "integer"}, 
                                "description": {"type": "string"}
                            },
                            "required": ["name", "value", "description"]
                        }
                    }
                },
                "save_triage_result": {
                    "sql_function_name": "save_triage_result",
                    "metadata": {
                        "description": "Saves triage assessment result",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "procurementId": {"type": "string", "format": "uuid"},
                                "color": {"type": "string", "enum": ["GRØNN", "GUL", "RØD"]},
                                "reasoning": {"type": "string"},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                            },
                            "required": ["procurementId", "color", "reasoning", "confidence"]
                        }
                    }
                },
                "set_procurement_status": {
                    "sql_function_name": "set_procurement_status",
                    "metadata": {
                        "description": "Updates procurement case status",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "procurementId": {"type": "string", "format": "uuid"},
                                "status": {"type": "string"}
                            },
                            "required": ["procurementId", "status"]
                        }
                    }
                },
                "save_protocol": {
                    "sql_function_name": "save_protocol",
                    "metadata": {
                        "description": "Saves a generated procurement protocol",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "procurementId": {"type": "string", "format": "uuid"},
                                "protocolContent": {"type": "string"},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                            },
                            "required": ["procurementId", "protocolContent", "confidence"]
                        }
                    }
                },
                "log_execution": {
                    "sql_function_name": "log_execution",
                    "metadata": {
                        "description": "Logs orchestrator execution history",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "procurementId": {"type": "string"},
                                "goalDescription": {"type": "string"},
                                "status": {"type": "string"},
                                "iterations": {"type": "integer"},
                                "finalState": {"type": "object"},
                                "executionHistory": {"type": "array"},
                                "agentId": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    }

async def load_acl_config(pool: asyncpg.Pool) -> Dict[str, Any]:
    """Loads ACL configuration from database with English method names."""
    try:
        async with pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'gateway_acl_config'
                );
            """)
            
            if not table_exists:
                logger.info("ACL config table not found, using default configuration")
                return {
                    "reasoning_orchestrator": {
                        "allowed_methods": [
                            "database.create_procurement",
                            "database.save_triage_result", 
                            "database.set_procurement_status",
                            "database.save_protocol",
                            "database.log_execution",
                            "agent.run_triage"
                        ]
                    }
                }
            
            rows = await conn.fetch("""
                SELECT agent_id, allowed_method
                FROM gateway_acl_config
                WHERE is_active = true
            """)
            
            acl = {}
            for row in rows:
                agent_id = row['agent_id']
                if agent_id not in acl:
                    acl[agent_id] = {"allowed_methods": []}
                acl[agent_id]["allowed_methods"].append(row['allowed_method'])
            
            return acl
    except Exception as e:
        logger.error("Failed to load ACL config", error=str(e))
        # Return default configuration on error
        return {
            "reasoning_orchestrator": {
                "allowed_methods": [
                    "database.create_procurement",
                    "database.save_triage_result", 
                    "database.set_procurement_status",
                    "database.save_protocol",
                    "database.log_execution",
                    "agent.run_triage"
                ]
            }
        }

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RPC Gateway...")
    try:
        # Create database connection pool with improved settings
        app_state.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            statement_cache_size=0,  # For pgbouncer compatibility
            max_inactive_connection_lifetime=300.0,  # Close inactive connections after 5 min
            timeout=10.0  # Connection timeout
        )
        logger.info("Database connection pool established")
        
        # Test connection
        try:
            async with app_state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                logger.info("Database connection verified")
        except Exception as e:
            logger.error("Failed to verify database connection", error=str(e))
            raise
        
        # Load configuration from database
        app_state.service_catalog = await load_service_catalog(app_state.db_pool)
        app_state.acl_config = await load_acl_config(app_state.db_pool)
        
        logger.info("Gateway configuration loaded", 
                   services=list(app_state.service_catalog.keys()),
                   agents=list(app_state.acl_config.keys()))
        
        yield
        
    finally:
        if app_state.db_pool:
            logger.info("Closing database connection pool...")
            try:
                # Use timeout to avoid infinite waiting
                await asyncio.wait_for(
                    app_state.db_pool.close(),
                    timeout=5.0  # 5 second timeout
                )
                logger.info("Database pool closed successfully")
            except asyncio.TimeoutError:
                logger.warning("Pool close timed out, terminating connections")
                # Force close connections
                app_state.db_pool.terminate()

# --- Execute RPC Method ---
async def execute_rpc_method(pool: asyncpg.Pool, 
                            service_name: str, 
                            function_key: str, 
                            params: Dict[str, Any]) -> Any:
    """Executes RPC method based on service type with enhanced validation."""
    service = app_state.service_catalog.get(service_name, {})
    service_type = service.get("type")
    function_info = service.get("functions", {}).get(function_key, {})
    
    if service_type == "postgres_rpc":
        # Database function with security validation
        sql_function = function_info.get("sql_function_name")
        if not sql_function:
            raise RPCError(ErrorCodes.INTERNAL_ERROR, 
                          f"SQL function name not found for {service_name}.{function_key}")
        
        # Apply security validation for procurement creation
        if function_key == "create_procurement":
            params = await app_state.security_validator.validate_procurement_input(params)
        
        async with pool.acquire() as conn:
            try:
                result = await conn.fetchval(
                    f"SELECT {sql_function}($1::jsonb)",
                    json.dumps(params)
                )
                return json.loads(result) if isinstance(result, str) else result
            except asyncpg.PostgresError as e:
                logger.error("Database operation failed", 
                           function=sql_function, 
                           error=str(e),
                           error_code=e.sqlstate)
                raise RPCError(ErrorCodes.INTERNAL_ERROR, f"Database operation failed: {e}")
            
    elif service_type == "http_endpoint":
        # HTTP-based agent/service
        endpoint_url = function_info.get("sql_function_name")  # URL stored here
        if not endpoint_url:
            raise RPCError(ErrorCodes.INTERNAL_ERROR, 
                          f"Endpoint URL not found for {service_name}.{function_key}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    endpoint_url,
                    json=params,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error("HTTP request failed", url=endpoint_url, error=str(e))
                raise RPCError(ErrorCodes.SERVICE_UNAVAILABLE, f"Service unavailable: {e}")
    
    else:
        raise RPCError(ErrorCodes.INTERNAL_ERROR, 
                      f"Unknown service type: {service_type}")

# --- Request Routing ---
async def route_method(method: str, params: Dict[str, Any], agent_id: str, request_id: str) -> Any:
    """Routes RPC methods to correct service with enhanced validation."""
    # Check ACL
    allowed_methods = app_state.acl_config.get(agent_id, {}).get("allowed_methods", [])
    if method not in allowed_methods:
        raise RPCError(ErrorCodes.UNAUTHORIZED, 
                      f"Agent '{agent_id}' is not authorized to call method '{method}'")

    # Parse method
    try:
        service_name, function_key = method.split('.', 1)
    except ValueError:
        raise RPCError(ErrorCodes.METHOD_NOT_FOUND, 
                      f"Invalid method format. Expected 'service.function', got '{method}'")

    # Find service
    service = app_state.service_catalog.get(service_name)
    if not service:
        raise RPCError(ErrorCodes.METHOD_NOT_FOUND, 
                      f"Service '{service_name}' not found")

    # Check function exists
    if function_key not in service.get("functions", {}):
        raise RPCError(ErrorCodes.METHOD_NOT_FOUND, 
                      f"Function '{function_key}' not found in service '{service_name}'")

    # Execute method
    result = await execute_rpc_method(app_state.db_pool, service_name, function_key, params)
    
    # Validate response for database methods
    if service.get("type") == "postgres_rpc":
        validated_result = await app_state.response_validator.validate(result, method)
        return validated_result
    
    return result

# --- FastAPI App ---
app = FastAPI(
    title="RPC Gateway", 
    version="2.0",
    description="Secure RPC Gateway for AI Platform - English API",
    lifespan=lifespan
)

@app.post("/rpc")
async def rpc_endpoint(request: Request, rpc_request: JsonRpcRequest) -> JsonRpcResponse:
    """Main endpoint for JSON-RPC requests with English API."""
    request_id = str(uuid.uuid4())
    
    # Bind request_id to logger
    request_logger = logger.bind(
        request_id=request_id,
        rpc_id=rpc_request.id,
        method=rpc_request.method
    )
    
    try:
        # Validate agent ID
        agent_id = request.headers.get("X-Agent-ID")
        if not agent_id:
            raise RPCError(ErrorCodes.UNAUTHORIZED, "X-Agent-ID header is required")
        
        request_logger = request_logger.bind(agent_id=agent_id)
        
        # Rate limiting with agent-specific limits
        if not await app_state.rate_limiter.check_rate_limit(agent_id):
            request_logger.warning("Rate limit exceeded")
            limit = app_state.rate_limiter.limits.get(agent_id, 60)
            raise RPCError(ErrorCodes.RATE_LIMITED, 
                          f"Rate limit exceeded. Max {limit} requests per minute for agent '{agent_id}'")
        
        request_logger.info("Processing RPC request")
        
        # Execute method
        result = await route_method(
            rpc_request.method, 
            rpc_request.params or {}, 
            agent_id,
            request_id
        )
        
        request_logger.info("RPC request completed successfully")
        
        return JsonRpcResponse(result=result, id=rpc_request.id)
        
    except RPCError as e:
        request_logger.warning("RPC error", 
                             error_code=e.code, 
                             error_message=e.message)
        return JsonRpcResponse(
            error={
                "code": e.code,
                "message": e.message,
                "data": e.data
            },
            id=rpc_request.id
        )
    except Exception as e:
        request_logger.error("Unexpected error", 
                           error=str(e), 
                           error_type=type(e).__name__,
                           exc_info=True)
        return JsonRpcResponse(
            error={
                "code": ErrorCodes.INTERNAL_ERROR,
                "message": "Internal server error",
                "data": {"request_id": request_id}
            },
            id=rpc_request.id
        )

@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint"""
    health = {
        "status": "healthy",
        "database": "unknown",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        if app_state.db_pool:
            async with app_state.db_pool.acquire() as conn:
                await asyncio.wait_for(
                    conn.fetchval("SELECT 1"),
                    timeout=5.0
                )
                health["database"] = "healthy"
        else:
            health["database"] = "not_initialized"
            health["status"] = "degraded"
    except Exception as e:
        health["status"] = "unhealthy"
        health["database"] = f"error: {str(e)}"
        logger.error("Health check failed", error=str(e))
    
    return HealthStatus(**health)

@app.get("/metrics")
async def metrics():
    """Enhanced metrics endpoint with agent-specific data."""
    metrics_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "agents": {},
        "services": list(app_state.service_catalog.keys()),
        "total_agents": len(app_state.acl_config),
        "rate_limiter": {
            "default_limit": app_state.rate_limiter.requests_per_minute,
            "custom_limits": app_state.rate_limiter.limits
        }
    }
    
    # Collect rate limit metrics with agent-specific limits
    for agent_id, requests in app_state.rate_limiter.agent_requests.items():
        limit = app_state.rate_limiter.limits.get(agent_id, 60)
        metrics_data["agents"][agent_id] = {
            "requests_last_minute": len(requests),
            "rate_limit": limit,
            "utilization_percentage": round((len(requests) / limit) * 100, 1)
        }
    
    return metrics_data

@app.get("/discover/{agent_id}")
async def discover_tools(agent_id: str):
    """Endpoint for agents to discover their available tools (English API)."""
    # Get available methods for the agent
    allowed_methods = app_state.acl_config.get(agent_id, {}).get("allowed_methods", [])
    
    # Build tool list with English method names
    tools = []
    for method in allowed_methods:
        try:
            # Split method name
            parts = method.split('.')
            if len(parts) != 2:
                logger.warning(f"Invalid method format: {method}")
                continue
                
            service_name, function_key = parts
            
            # Create basic tool entry
            tool = {
                "method": method,
                "service_type": "unknown",
                "sql_function_name": function_key,
                "metadata": {},
                "description": f"Function: {function_key}",
                "input_schema": {},
                "output_schema": {}
            }
            
            # Enrich with info from service catalog if available
            service = app_state.service_catalog.get(service_name)
            if service and isinstance(service, dict):
                tool["service_type"] = service.get("type", "postgres_rpc")
                
                # Handle functions that can be dict or something else
                functions = service.get("functions")
                if functions and isinstance(functions, dict):
                    function_info = functions.get(function_key)
                    
                    if function_info:
                        if isinstance(function_info, str):
                            # Old structure
                            tool["sql_function_name"] = function_info
                        elif isinstance(function_info, dict):
                            # New structure
                            tool["sql_function_name"] = function_info.get("sql_function_name", function_key)
                            metadata = function_info.get("metadata", {})
                            if isinstance(metadata, dict):
                                tool["metadata"] = metadata
                                tool["description"] = metadata.get("description", tool["description"])
                                tool["input_schema"] = metadata.get("input_schema", {})
                                tool["output_schema"] = metadata.get("output_schema", {})
            
            tools.append(tool)
            
        except Exception as e:
            logger.error(f"Error processing method {method}: {str(e)}", exc_info=True)
            # Add minimal entry even on error
            tools.append({
                "method": method,
                "service_type": "unknown",
                "sql_function_name": method,
                "metadata": {},
                "description": f"Method: {method}",
                "input_schema": {},
                "output_schema": {}
            })
    
    return {"agent_id": agent_id, "tools": tools}

@app.post("/reload-config")
async def reload_configuration(request: Request):
    """Endpoint to reload configuration with cache invalidation."""
    # Requires admin authentication
    admin_token = request.headers.get("X-Admin-Token")
    if admin_token != os.getenv("ADMIN_TOKEN"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        if app_state.db_pool:
            # Clear any internal caches before reloading
            app_state.service_catalog.clear()
            app_state.acl_config.clear()
            
            # Reload from database
            app_state.service_catalog = await load_service_catalog(app_state.db_pool)
            app_state.acl_config = await load_acl_config(app_state.db_pool)
            
            logger.info("Configuration reloaded successfully", 
                       services=list(app_state.service_catalog.keys()),
                       agents=list(app_state.acl_config.keys()))
            return {
                "status": "success", 
                "message": "Configuration reloaded",
                "services_loaded": len(app_state.service_catalog),
                "agents_configured": len(app_state.acl_config)
            }
    except Exception as e:
        logger.error("Failed to reload configuration", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reload configuration")

@app.get("/debug/config")
async def debug_configuration(request: Request):
    """Debug endpoint to inspect current configuration (admin only)."""
    admin_token = request.headers.get("X-Admin-Token")
    if admin_token != os.getenv("ADMIN_TOKEN"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return {
        "service_catalog": app_state.service_catalog,
        "acl_config": app_state.acl_config,
        "rate_limits": app_state.rate_limiter.limits,
        "active_requests": {
            agent_id: len(requests) 
            for agent_id, requests in app_state.rate_limiter.agent_requests.items()
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)