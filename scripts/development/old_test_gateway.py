# test_gateway.py
import asyncio
import httpx
import json

async def test_gateway():
    async with httpx.AsyncClient() as client:
        # Test health
        health = await client.get("http://localhost:8000/health")
        print("Health:", health.json())
        
        # Test RPC call
        rpc_request = {
            "jsonrpc": "2.0",
            "method": "database.sett_status",
            "params": {
                "request_id": "test-123",
                "status": "PENDING"
            },
            "id": 1
        }
        
        response = await client.post(
            "http://localhost:8000/rpc",
            json=rpc_request,
            headers={"X-Agent-ID": "anskaffelsesassistenten"}
        )
        print("RPC Response:", response.json())

if __name__ == "__main__":
    asyncio.run(test_gateway())