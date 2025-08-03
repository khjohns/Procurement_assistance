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

# --- Konfigurasjon ---
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in the environment variables.")

logger = structlog.get_logger()

# --- Pydantic Modeller ---
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

# --- Feilhåndtering ---
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
    # Egendefinerte
    UNAUTHORIZED = -32001
    SERVICE_UNAVAILABLE = -32002
    RATE_LIMITED = -32003
    TIMEOUT_ERROR = -32004

# --- Rate Limiting ---
class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.agent_requests = defaultdict(list)
    
    async def check_rate_limit(self, agent_id: str) -> bool:
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Fjern gamle requests
        self.agent_requests[agent_id] = [
            req_time for req_time in self.agent_requests[agent_id]
            if req_time > minute_ago
        ]
        
        if len(self.agent_requests[agent_id]) >= self.requests_per_minute:
            return False
        
        self.agent_requests[agent_id].append(now)
        return True

# --- Response Validation ---
class ResponseValidator:
    """Validerer RPC-responser basert på metode"""
    
    @staticmethod
    async def validate(result: Any, method: str) -> Any:
        """Validerer at RPC-responsen er i forventet format"""
        validators = {
            "database.lagre_triage_resultat": ResponseValidator._validate_lagre_triage,
            "database.sok_oslomodell_krav": ResponseValidator._validate_sok_resultat,
            "database.sett_status": ResponseValidator._validate_status_update
        }
        
        validator = validators.get(method)
        if validator:
            return await validator(result)
        return result
    
    @staticmethod
    async def _validate_lagre_triage(result: Any) -> Dict[str, Any]:
        """Validerer respons fra lagre_triage_resultat"""
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Invalid JSON response from database")
        
        if not isinstance(result, dict):
            raise RPCError(ErrorCodes.INTERNAL_ERROR, "Expected dict response")
        
        required_fields = ["status", "resultat_id"]
        for field in required_fields:
            if field not in result:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, f"Missing required field: {field}")
        
        return result
    
    @staticmethod
    async def _validate_sok_resultat(result: Any) -> List[Dict[str, Any]]:
        """Validerer respons fra søkefunksjoner"""
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
        """Validerer respons fra statusoppdatering"""
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                raise RPCError(ErrorCodes.INTERNAL_ERROR, "Invalid JSON response from database")
        
        return result

# --- Database og App State ---
class AppState:
    db_pool: Optional[asyncpg.Pool] = None
    service_catalog: Dict[str, Any] = {}
    acl_config: Dict[str, Any] = {}
    rate_limiter: RateLimiter = RateLimiter()
    response_validator: ResponseValidator = ResponseValidator()

app_state = AppState()

# --- Service Catalog Management ---
async def load_service_catalog(pool: asyncpg.Pool) -> Dict[str, Any]:
    """Laster service catalog fra database"""
    try:
        async with pool.acquire() as conn:
            # Sjekk om tabellen eksisterer
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'gateway_service_catalog'
                );
            """)
            
            if not table_exists:
                logger.info("Service catalog table not found, using default configuration")
                return {
                    "database": {
                        "type": "postgres_rpc",
                        "functions": {
                            "lagre_triage_resultat": "lagre_triage_resultat",
                            "sett_status": "sett_status",
                            "sok_oslomodell_krav": "sok_oslomodell_krav"
                        }
                    }
                }
            
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
                catalog[service_name]["functions"][row['function_key']] = row['sql_function_name']
            
            return catalog
    except Exception as e:
        logger.error("Failed to load service catalog", error=str(e))
        # Returner default konfigurasjon ved feil
        return {
            "database": {
                "type": "postgres_rpc",
                "functions": {
                    "lagre_triage_resultat": "lagre_triage_resultat",
                    "sett_status": "sett_status",
                    "sok_oslomodell_krav": "sok_oslomodell_krav"
                }
            }
        }

async def load_acl_config(pool: asyncpg.Pool) -> Dict[str, Any]:
    """Laster ACL konfigurasjon fra database"""
    try:
        async with pool.acquire() as conn:
            # Sjekk om tabellen eksisterer
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'gateway_acl_config'
                );
            """)
            
            if not table_exists:
                logger.info("ACL config table not found, using default configuration")
                return {
                    "anskaffelsesassistenten": {
                        "allowed_methods": [
                            "database.lagre_triage_resultat", 
                            "database.sok_oslomodell_krav",
                            "database.sett_status"
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
        # Returner default konfigurasjon ved feil
        return {
            "anskaffelsesassistenten": {
                "allowed_methods": [
                    "database.lagre_triage_resultat", 
                    "database.sok_oslomodell_krav",
                    "database.sett_status"
                ]
            }
        }

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RPC Gateway...")
    try:
        # Opprett database connection pool med forbedrede innstillinger
        app_state.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            statement_cache_size=0,  # For pgbouncer
            max_inactive_connection_lifetime=300.0,  # Lukk inaktive connections etter 5 min
            timeout=10.0  # Connection timeout
            # FJERNET: pool_recycle=3600 - ikke støttet i asyncpg
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
        
        # Last konfigurasjon fra database
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
                # Bruk timeout for å unngå evig venting
                await asyncio.wait_for(
                    app_state.db_pool.close(),
                    timeout=5.0  # 5 sekunder timeout
                )
                logger.info("Database pool closed successfully")
            except asyncio.TimeoutError:
                logger.warning("Pool close timed out, terminating connections")
                # Tving lukking av connections
                app_state.db_pool.terminate()

async def execute_postgres_rpc(function_name: str, params: Dict[str, Any]) -> Any:
    """Utfører en PostgreSQL RPC-funksjon med timeout og feilhåndtering"""
    if not app_state.db_pool:
        raise RPCError(ErrorCodes.SERVICE_UNAVAILABLE, "Database service not available")

    # Bygg parameterisert query med posisjonelle argumenter
    param_placeholders = ', '.join([f'${i+1}' for i in range(len(params))])
    sql_query = f"SELECT {function_name}({param_placeholders});"
    
    logger.info("Executing PostgreSQL RPC", 
               sql_function=function_name, 
               param_count=len(params))

    connection = None
    try:
        # Acquire connection med timeout
        connection = await asyncio.wait_for(
            app_state.db_pool.acquire(),
            timeout=5.0
        )
        
        # Utfør query med timeout
        result = await asyncio.wait_for(
            connection.fetchval(sql_query, *params.values()),
            timeout=30.0
        )
        
        logger.info("RPC execution completed", 
                   function=function_name,
                   result_type=type(result).__name__)
        
        # --- VIKTIG ENDRING HER ---
        # Sikrer at resultatet er et parset objekt, ikke en streng.
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                logger.warning("Result from DB was a string but failed JSON parsing", db_result=result)
                # Returnerer strengen som den er hvis den ikke er gyldig JSON
                return result
        # --- SLUTT PÅ ENDRING ---

        return result
        
    except asyncio.TimeoutError:
        logger.error("RPC timeout", function=function_name)
        raise RPCError(ErrorCodes.TIMEOUT_ERROR, 
                      f"Function '{function_name}' timed out")
    except asyncpg.PostgresError as e:
        logger.error("PostgreSQL Error", 
                    error=str(e), 
                    error_type=type(e).__name__,
                    sql=sql_query)
        raise RPCError(ErrorCodes.INTERNAL_ERROR, 
                      f"Database error: {str(e)}")
    finally:
        # Sørg for at connection alltid frigjøres
        if connection:
            await app_state.db_pool.release(connection)

# --- Request Routing ---
async def route_method(method: str, params: Dict[str, Any], agent_id: str, request_id: str) -> Any:
    """Router RPC-metoder til riktig tjeneste med validering"""
    # Sjekk ACL
    allowed_methods = app_state.acl_config.get(agent_id, {}).get("allowed_methods", [])
    if method not in allowed_methods:
        raise RPCError(ErrorCodes.UNAUTHORIZED, 
                      f"Agent '{agent_id}' is not authorized to call method '{method}'")

    # Parse metode
    try:
        service_name, function_key = method.split('.', 1)
    except ValueError:
        raise RPCError(ErrorCodes.METHOD_NOT_FOUND, 
                      f"Invalid method format. Expected 'service.function', got '{method}'")

    # Finn tjeneste
    service = app_state.service_catalog.get(service_name)
    if not service:
        raise RPCError(ErrorCodes.METHOD_NOT_FOUND, 
                      f"Service '{service_name}' not found")

    # Håndter ulike tjenestetyper
    if service["type"] == "postgres_rpc":
        sql_function_name = service["functions"].get(function_key)
        if not sql_function_name:
            raise RPCError(ErrorCodes.METHOD_NOT_FOUND, 
                          f"Function '{function_key}' not found in service '{service_name}'")
        
        # Utfør RPC
        result = await execute_postgres_rpc(sql_function_name, params)
        
        # Valider respons
        validated_result = await app_state.response_validator.validate(result, method)
        
        return validated_result
    else:
        raise RPCError(ErrorCodes.INTERNAL_ERROR, 
                      f"Unsupported service type: {service['type']}")

# --- FastAPI App ---
app = FastAPI(
    title="RPC Gateway", 
    version="2.0",
    description="Secure RPC Gateway for AI Platform",
    lifespan=lifespan
)

@app.post("/rpc")
async def rpc_endpoint(request: Request, rpc_request: JsonRpcRequest) -> JsonRpcResponse:
    """Hovedendepunkt for JSON-RPC requests"""
    request_id = str(uuid.uuid4())
    
    # Bind request_id til logger
    request_logger = logger.bind(
        request_id=request_id,
        rpc_id=rpc_request.id,
        method=rpc_request.method
    )
    
    try:
        # Valider agent ID
        agent_id = request.headers.get("X-Agent-ID")
        if not agent_id:
            raise RPCError(ErrorCodes.UNAUTHORIZED, "X-Agent-ID header is required")
        
        request_logger = request_logger.bind(agent_id=agent_id)
        
        # Rate limiting
        if not await app_state.rate_limiter.check_rate_limit(agent_id):
            request_logger.warning("Rate limit exceeded")
            raise RPCError(ErrorCodes.RATE_LIMITED, 
                          f"Rate limit exceeded. Max {app_state.rate_limiter.requests_per_minute} requests per minute")
        
        request_logger.info("Processing RPC request")
        
        # Utfør metode
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
    """Basic metrics endpoint"""
    metrics_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "agents": {},
        "services": list(app_state.service_catalog.keys()),
        "total_agents": len(app_state.acl_config)
    }
    
    # Samle rate limit metrics
    for agent_id, requests in app_state.rate_limiter.agent_requests.items():
        metrics_data["agents"][agent_id] = {
            "requests_last_minute": len(requests)
        }
    
    return metrics_data

@app.post("/reload-config")
async def reload_configuration(request: Request):
    """Endpoint for å laste konfigurasjon på nytt"""
    # Krever admin-autentisering
    admin_token = request.headers.get("X-Admin-Token")
    if admin_token != os.getenv("ADMIN_TOKEN"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        if app_state.db_pool:
            app_state.service_catalog = await load_service_catalog(app_state.db_pool)
            app_state.acl_config = await load_acl_config(app_state.db_pool)
            
            logger.info("Configuration reloaded successfully")
            return {"status": "success", "message": "Configuration reloaded"}
    except Exception as e:
        logger.error("Failed to reload configuration", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reload configuration")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)