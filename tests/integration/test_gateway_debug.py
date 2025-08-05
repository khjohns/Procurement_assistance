# test_gateway_debug.py
import httpx
import asyncio
import json

async def test_gateway():
    """Test gateway endpoints direkte"""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # 1. Test health
        print("=== Testing Health Endpoint ===")
        try:
            response = await client.get(f"{base_url}/health")
            print(f"Health Status: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Health check failed: {e}")
        
        # 2. Test metrics
        print("\n=== Testing Metrics Endpoint ===")
        try:
            response = await client.get(f"{base_url}/metrics")
            print(f"Metrics Status: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Metrics failed: {e}")
        
        # 3. Test discover for reasoning_orchestrator
        print("\n=== Testing Discover Endpoint ===")
        try:
            response = await client.get(f"{base_url}/discover/reasoning_orchestrator")
            print(f"Discover Status: {response.status_code}")
            data = response.json()
            print(f"Agent: {data['agent_id']}")
            print(f"Number of tools: {len(data['tools'])}")
            
            if data['tools']:
                print("\nFirst 3 tools:")
                for i, tool in enumerate(data['tools'][:3]):
                    print(f"\n{i+1}. {tool['method']}")
                    print(f"   Type: {tool['service_type']}")
                    print(f"   Description: {tool['description']}")
            else:
                print("No tools found!")
                
        except Exception as e:
            print(f"Discover failed: {e}")
        
        # 4. Test a simple RPC call
        print("\n=== Testing RPC Endpoint ===")
        try:
            # Test med database.sett_status som et eksempel
            rpc_request = {
                "jsonrpc": "2.0",
                "method": "database.sett_status",
                "params": {
                    "request_id": "00000000-0000-0000-0000-000000000000",  # Dummy UUID
                    "status": "TEST"
                },
                "id": 1
            }
            
            response = await client.post(
                f"{base_url}/rpc",
                json=rpc_request,
                headers={"X-Agent-ID": "reasoning_orchestrator"}
            )
            print(f"RPC Status: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
            
        except Exception as e:
            print(f"RPC test failed: {e}")

if __name__ == "__main__":
    print("Testing Gateway Endpoints...\n")
    asyncio.run(test_gateway())