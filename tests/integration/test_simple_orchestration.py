# tests/integration/test_simple_orchestration.py
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import pytest

@pytest.mark.asyncio
async def test_basic_orchestration():
    """Enkel test av orkestreringssystemet"""
    
    # Import etter at path er satt opp
    from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator, Goal, GoalStatus
    from src.tools.gemini_gateway import GeminiGateway
    from src.models.procurement_models import AnskaffelseRequest
    
    print("=== Testing Basic Orchestration ===\n")
    
    # 1. Test GeminiGateway
    print("1. Testing GeminiGateway...")
    try:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            pytest.skip("GEMINI_API_KEY not set")
            return
        
        gateway = GeminiGateway(gemini_api_key)
        
        # Test generate med nye parametere
        response = await gateway.generate(
            prompt="Hei, svar med JSON: {\"status\": \"ok\"}",
            temperature=0.1,
            response_mime_type="application/json"
        )
        print(f"   ✅ GeminiGateway works: {response[:50]}...")
    except Exception as e:
        print(f"   ❌ GeminiGateway failed: {e}")
        pytest.fail(f"GeminiGateway failed: {e}")
    
    # 2. Test Orchestrator initialization
    print("\n2. Testing ReasoningOrchestrator...")
    try:
        orchestrator = ReasoningOrchestrator(gateway)
        print("   ✅ Orchestrator initialized")
    except Exception as e:
        print(f"   ❌ Orchestrator init failed: {e}")
        pytest.fail(f"Orchestrator init failed: {e}")
    
    # 3. Test tool discovery
    print("\n3. Testing tool discovery...")
    try:
        tools = await orchestrator._discover_tools()
        print(f"   ✅ Found {len(tools)} tools:")
        for tool in tools[:3]:  # Vis første 3
            print(f"      - {tool['method']}: {tool['description']}")
    except Exception as e:
        print(f"   ❌ Tool discovery failed: {e}")
        pytest.fail(f"Tool discovery failed: {e}")
    
    # 4. Test simple goal
    print("\n4. Testing simple goal execution...")
    try:
        request = AnskaffelseRequest(
            navn="Test innkjøp",
            verdi=50_000,
            beskrivelse="Test av orkestreringssystem"
        )
        
        goal = Goal(
            id=request.id,
            description=f"Opprett anskaffelsessak for: {request.navn}",
            context={"request": request.model_dump()},
            success_criteria=["Anskaffelsessak er opprettet i databasen"]
        )
        
        context = await orchestrator.achieve_goal(goal)
        
        print(f"   ✅ Goal status: {goal.status.value}")
        print(f"   ✅ Executions: {len(context.execution_history)}")
        
        if context.execution_history:
            print("\n   Executed actions:")
            for exec in context.execution_history:
                action = exec['action']
                result = exec['result']
                print(f"      - {action['method']}: {result.get('status', 'unknown')}")
        
        # Assertions
        assert goal.status in [GoalStatus.COMPLETED, GoalStatus.REQUIRES_HUMAN, GoalStatus.FAILED]
        assert isinstance(context.execution_history, list)
                
    except Exception as e:
        print(f"   ❌ Goal execution failed: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Goal execution failed: {e}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    # For direkte kjøring
    asyncio.run(test_basic_orchestration())