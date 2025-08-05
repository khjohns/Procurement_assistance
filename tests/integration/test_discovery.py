# test_discovery.py - Kjør dette for å teste at discovery endpoint fungerer
import httpx
import asyncio
import json

async def test_discovery():
    """Test discovery endpoint for reasoning_orchestrator"""
    
    async with httpx.AsyncClient() as client:
        try:
            # Test discovery endpoint
            response = await client.get(
                "http://localhost:8000/discover/reasoning_orchestrator"
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\nAgent ID: {data['agent_id']}")
                print(f"Number of tools: {len(data['tools'])}")
                
                print("\nAvailable tools:")
                for i, tool in enumerate(data['tools'], 1):
                    print(f"\n{i}. {tool['method']}")
                    print(f"   Type: {tool['service_type']}")
                    print(f"   Description: {tool['description']}")
                    if tool.get('input_schema'):
                        print(f"   Input Schema: {json.dumps(tool['input_schema'], indent=4)}")
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Connection error: {e}")
            print("Make sure the gateway is running on http://localhost:8000")

async def test_health():
    """Test health endpoint"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/health")
            print("\n=== Health Check ===")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Health check failed: {e}")

if __name__ == "__main__":
    print("Testing Gateway Discovery Endpoint...")
    asyncio.run(test_discovery())
    asyncio.run(test_health())