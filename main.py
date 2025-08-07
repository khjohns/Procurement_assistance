# main.py - Full oppdatering
import os
import asyncio
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ENDRE: Importer Enhanced LLM Gateway
from src.tools.enhanced_llm_gateway import LLMGateway  # Ikke GeminiGateway

from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator, Goal, GoalStatus
from src.models.procurement_models import ProcurementRequest

load_dotenv()

async def run_full_triage():
    print("\n=== Testing with Enhanced LLM Gateway ===\n")

    # ENDRE: Bruk LLMGateway direkte
    llm_gateway = LLMGateway()  # Automatisk bruker GEMINI_API_KEY fra env
    
    # Orchestrator tar imot llm_gateway
    orchestrator = ReasoningOrchestrator(llm_gateway)
    
    request = ProcurementRequest(
        name="Innkjøp av nye servere",
        value=500_000,
        description="Erstatte hele serverparken."
    )
    
    goal = Goal(
        id=request.id,
        description=f"Complete procurement process for: '{request.name}'",
        context={"request": request.model_dump()},
        success_criteria=[
            "Procurement case created in the database",
            "Triage result is successfully saved to the database"
        ]
    )
    
    print(f"Goal: {goal.description}")
    print(f"Procurement ID: {request.id}\n")
    
    # Kjør orkestrering
    context = await orchestrator.achieve_goal(goal)
    
    print(f"\n--- Result ---")
    print(f"Status: {goal.status.value}")
    print(f"Iterations: {len(context.execution_history)}")
    
    # Vis metrics fra enhanced gateway
    metrics = llm_gateway.get_metrics()
    print(f"\nLLM Metrics:")
    print(f"- Total calls: {metrics['total_calls']}")
    print(f"- Success rate: {metrics['success_rate']:.1%}")
    print(f"- Estimated cost: ${metrics['estimated_cost_usd']:.4f}")

if __name__ == "__main__":
    asyncio.run(run_full_triage())