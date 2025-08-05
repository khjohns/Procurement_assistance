# main.py (Refactored)
import os
import asyncio
import sys
from dotenv import load_dotenv

# Add project root to path to allow imports from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator, Goal, GoalStatus
from src.tools.gemini_gateway import GeminiGateway
from src.models.procurement_models import ProcurementRequest

load_dotenv()

async def run_full_triage():
    """
    Tests a complete, refactored orchestration flow.
    """
    print("\n=== Testing Refactored Full Triage Orchestration ===\n")

    # Setup
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    assert gemini_api_key, "GEMINI_API_KEY is not set"

    gateway = GeminiGateway(gemini_api_key)
    orchestrator = ReasoningOrchestrator(gateway)

    request = ProcurementRequest(
        name="Innkjøp av nytt IKT-system for saksbehandling",
        value=750_000,
        description="Vi skal erstatte vårt gamle saksbehandlingssystem..."
    )

    goal = Goal(
        id=request.id,
        description=f"Complete a standard procurement process for: '{request.name}'.",
        context={"request": request.model_dump()},
        success_criteria=[
            "The procurement case has been created in the database.",
            "A triage assessment (GRØNN, GUL, or RØD) has been performed.",
            "The triage result has been saved to the database."
        ]
    )

    print(f"Goal: {goal.description}")
    print(f"Procurement ID: {request.id}\n")

    # Run orchestration
    context = await orchestrator.achieve_goal(goal)

    print(f"\n--- Orchestration Result ---")
    print(f"Final Status: {goal.status.value}")
    print(f"Iterations: {len(context.execution_history)}")

    action_log = [exec['action']['method'] for exec in context.execution_history]
    print(f"Action Log: {action_log}")

    assert goal.status == GoalStatus.COMPLETED, f"Goal failed with status {goal.status.value}"
    
    # Assert that the new, refactored methods were called
    assert 'database.create_procurement' in action_log
    assert 'agent.run_triage' in action_log
    assert 'database.save_triage_result' in action_log
    
    print("\n✅ Orchestration completed and key actions were performed.")

    triage_result_data = {}
    for exec in context.execution_history:
        if exec['action']['method'] == 'database.save_triage_result':
            triage_result_data = exec['action']['parameters']
            break
            
    assert triage_result_data, "Triage result was not found in the execution history"
    assert triage_result_data.get('color') in ['GRØNN', 'GUL', 'RØD']
    assert len(triage_result_data.get('reasoning', '')) > 10
    
    print(f"Stored Triage Color: {triage_result_data.get('color')}")
    print(f"✅ Triage result looks valid and was stored.")

if __name__ == "__main__":
    print("NOTE: This script assumes the database has been set up with the refactored schema.")
    print("Run 'python scripts/setup/run_db_setup.py setup' first.")
    asyncio.run(run_full_triage())
