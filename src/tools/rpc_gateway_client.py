# tools/rpc_gateway_client.py
import httpx
import structlog
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Assuming models are now in a central place
from src.models.procurement_models import TriageResult, ProcurementRequest

load_dotenv()
logger = structlog.get_logger()

class RPCError(Exception):
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"RPC Error {code}: {message}")

class RPCGatewayClient:
    def __init__(self, agent_id: str, **kwargs):
        base_url = kwargs.get("base_url") or kwargs.get("gateway_url")
        self.base_url = base_url or os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
        self.agent_id = agent_id
        self.client = httpx.AsyncClient(base_url=self.base_url, headers={"X-Agent-ID": self.agent_id}, timeout=30.0)
        self._request_id = 0
        logger.info("RPCGatewayClient initialized", base_url=self.base_url, agent_id=self.agent_id)
    
    async def __aenter__(self):
        await self.client.__aenter__()
        try:
            health = await self.client.get("/health")
            if health.json().get("database") != "healthy":
                logger.warning("Gateway database not healthy", health=health.json())
        except Exception as e:
            logger.error("Failed to check gateway health", error=str(e))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self._request_id += 1
        request_data = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": self._request_id}
        logger.info("Making RPC call", method=method, request_id=self._request_id)
        try:
            response = await self.client.post("/rpc", json=request_data)
            response.raise_for_status()
            result = response.json()
            if result.get("error") is not None:
                error = result["error"]
                raise RPCError(code=error.get("code", -1), message=error.get("message", "Unknown error"), data=error.get("data"))
            logger.info("RPC call successful", method=method, request_id=self._request_id)
            return result.get("result")
        except httpx.HTTPError as e:
            logger.error("HTTP error during RPC call", method=method, error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during RPC call", method=method, error=str(e), exc_info=True)
            raise

    # --- New, refactored convenience methods ---

    async def create_procurement(self, request: ProcurementRequest) -> Dict[str, Any]:
        params = {"name": request.name, "value": request.value, "description": request.description}
        return await self.call("database.create_procurement", params)

    async def save_triage_result(self, procurement_id: str, triage_result: TriageResult) -> Dict[str, Any]:
        params = {
            "procurementId": procurement_id,
            "color": triage_result.color.value,  # Use enum value
            "reasoning": triage_result.reasoning,
            "confidence": triage_result.confidence,
            "riskFactors": triage_result.risk_factors,
            "mitigationMeasures": triage_result.mitigation_measures,
            "requiresSpecialAttention": triage_result.requires_special_attention,
            "escalationRecommended": triage_result.escalation_recommended
        }
        return await self.call("database.save_triage_result", params)

    async def set_procurement_status(self, procurement_id: str, status: str) -> Dict[str, Any]:
        params = {"procurementId": procurement_id, "status": status}
        return await self.call("database.set_procurement_status", params)

    async def save_protocol(self, procurement_id: str, protocol_content: str, confidence: float) -> Dict[str, Any]:
        params = {"procurementId": procurement_id, "protocolContent": protocol_content, "confidence": confidence}
        return await self.call("database.save_protocol", params)
