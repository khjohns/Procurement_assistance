# tools/rpc_client.py
import httpx
from typing import Dict, Any

class RPCClient:
    def __init__(self, base_url: str, agent_id: str, timeout: int = 30):
        self.base_url = base_url
        self.agent_id = agent_id
        self.timeout = timeout
        self.headers = {
            "X-Agent-ID": self.agent_id,
            "Content-Type": "application/json"
        }

    async def call(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Sender et JSON-RPC kall til gatewayen."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1  # ID kan gjøres mer sofistikert ved behov
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout
                )
                response.raise_for_status()  # Kaster feil for 4xx/5xx statuskoder

                data = response.json()
                if "error" in data:
                    # Håndter RPC-feil fra gatewayen
                    raise ConnectionError(f"RPC Error: {data['error']['message']} (Code: {data['error']['code']})")

                return data.get("result")

            except httpx.HTTPStatusError as e:
                raise ConnectionError(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise ConnectionError(f"An unexpected error occurred: {e}")