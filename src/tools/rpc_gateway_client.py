# tools/rpc_gateway_client.py
import httpx
import structlog
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()

class RPCError(Exception):
    """Custom exception for RPC errors"""
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"RPC Error {code}: {message}")

class RPCGatewayClient:
    """Client for communicating with the RPC Gateway"""
    
    def __init__(self, base_url: str = None, agent_id: str = "anskaffelsesassistenten"):
        self.base_url = base_url or os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
        self.agent_id = agent_id
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-Agent-ID": self.agent_id},
            timeout=30.0
        )
        self._request_id = 0
        logger.info("RPCGatewayClient initialized", 
                   base_url=self.base_url, 
                   agent_id=self.agent_id)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.client.__aenter__()
        # Test connection
        try:
            health = await self.client.get("/health")
            health_data = health.json()
            if health_data.get("database") != "healthy":
                logger.warning("Gateway database not healthy", health=health_data)
        except Exception as e:
            logger.error("Failed to check gateway health", error=str(e))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make an RPC call to the gateway"""
        self._request_id += 1
        
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._request_id
        }
        
        logger.info("Making RPC call", 
                   method=method, 
                   request_id=self._request_id,
                   params_keys=list(params.keys()) if params else [])
        
        try:
            response = await self.client.post("/rpc", json=request_data)
            response.raise_for_status()
            
            result = response.json()
            
            # --- KORREKSJON HER ---
            # Sjekk om 'error'-feltet har en reell verdi, ikke bare om nøkkelen finnes
            if result.get("error") is not None:
                error = result["error"]
                raise RPCError(
                    code=error.get("code", -1),
                    message=error.get("message", "Unknown error"),
                    data=error.get("data")
                )
            # --- SLUTT PÅ KORREKSJON ---
            
            logger.info("RPC call successful", 
                       method=method,
                       request_id=self._request_id)
            
            return result.get("result")
            
        except httpx.HTTPError as e:
            logger.error("HTTP error during RPC call", 
                        method=method,
                        error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during RPC call",
                        method=method,
                        error=str(e),
                        exc_info=True)
            raise
    
    # Convenience methods for specific operations
    async def lagre_triage_resultat(self, request_id: str, triage_result) -> Dict[str, Any]:
        """Lagre triageresultat"""
        params = {
            "request_id": request_id,
            "farge": triage_result.farge,
            "begrunnelse": triage_result.begrunnelse,
            "confidence": triage_result.confidence
        }
        return await self.call("database.lagre_triage_resultat", params)
    
    async def sett_status(self, request_id: str, status: str) -> Dict[str, Any]:
        """Sett status på request"""
        params = {
            "request_id": request_id,
            "status": status
        }
        return await self.call("database.sett_status", params)
    
    async def sok_oslomodell_krav(self, sokevektor: list, kategori: str = None, 
                                  maks_resultater: int = 5) -> Dict[str, Any]:
        """Søk i Oslomodell-krav"""
        params = {
            "sokevektor": sokevektor,
            "maks_resultater": maks_resultater
        }
        if kategori:
            params["kategori"] = kategori
        
        return await self.call("database.sok_oslomodell_krav", params)
    
    async def lagre_protokoll(self, request_id: str, protokoll_tekst: str, 
                             confidence: float) -> Dict[str, Any]:
        """Lagre protokoll"""
        params = {
            "request_id": request_id,
            "protokoll_tekst": protokoll_tekst,
            "confidence": confidence
        }
        return await self.call("database.lagre_protokoll", params)