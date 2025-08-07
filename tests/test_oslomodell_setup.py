#test_oslomodell_setup.py
import asyncio
import httpx
from src.tools.rpc_gateway_client import RPCGatewayClient

async def verify():
    # 1. Check agent discovery
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:8000/discover/oslomodell_agent")
        data = resp.json()
        methods = [t['method'] for t in data['tools']]
        
        assert 'database.search_knowledge_documents' in methods
        print("✅ Agent has knowledge access")
    
    # 2. Test knowledge search
    async with RPCGatewayClient("oslomodell_agent") as rpc:
        result = await rpc.call("database.list_knowledge_documents", {})
        docs = result.get('documents', [])
        
        assert len(docs) >= 3
        print(f"✅ Found {len(docs)} knowledge documents")
    
    print("\n🎉 Oslomodell setup verified!")

asyncio.run(verify())