# test_database_orchestration.py
import asyncio
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

# Bruk pytest.mark.asyncio, IKKE pytest.mark.anyio
@pytest.mark.asyncio

async def test_database_orchestration():
    """Test orkestrering med kun database-verktøy"""
    
    from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator, Goal, GoalStatus
    from src.tools.gemini_gateway import GeminiGateway
    from src.models.procurement_models import AnskaffelseRequest
    
    print("=== Testing Database-Only Orchestration ===\n")
    
    # Setup
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    gateway = GeminiGateway(gemini_api_key)
    orchestrator = ReasoningOrchestrator(gateway)
    
    # Enkel test-case
    request = AnskaffelseRequest(
        navn="Testinnkjøp av kontorrekvisita",
        verdi=25_000,
        beskrivelse="Innkjøp av penner, papir og annet kontormateriell"
    )
    
    # Enkelt mål - bare opprett saken
    goal = Goal(
        id=request.id,
        description=f"Opprett anskaffelsessak for: {request.navn}",
        context={"request": request.model_dump()},
        success_criteria=[
            "Anskaffelsessak er opprettet i databasen med unik ID"
        ]
    )
    
    print(f"Goal: {goal.description}")
    print(f"Request ID: {request.id}\n")
    
    try:
        # Kjør orkestrering
        context = await orchestrator.achieve_goal(goal)
        
        print(f"\nResult:")
        print(f"  Status: {goal.status.value}")
        print(f"  Iterations: {len(context.execution_history)}")
        
        if context.execution_history:
            print("\nExecuted actions:")
            for i, exec in enumerate(context.execution_history):
                action = exec['action']
                result = exec['result']
                print(f"  {i+1}. {action['method']}")
                print(f"     Status: {result.get('status', 'unknown')}")
                if result.get('status') == 'success' and result.get('result'):
                    print(f"     Result: {result['result']}")
        
        # Hvis vi fikk en request_id, prøv å oppdatere status
        if goal.status == GoalStatus.COMPLETED:
            print("\n✅ Goal completed successfully!")
            
            # Se om vi kan finne request_id i context
            for exec in context.execution_history:
                if exec['action']['method'] == 'database.opprett_anskaffelse':
                    if exec['result'].get('status') == 'success':
                        created_id = exec['result'].get('result', {}).get('request_id')
                        if created_id:
                            print(f"Created request ID: {created_id}")
                            break
        else:
            print(f"\n⚠️ Goal ended with status: {goal.status.value}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_database_orchestration())