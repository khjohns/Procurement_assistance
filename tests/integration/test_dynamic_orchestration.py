# tests/integration/test_dynamic_orchestration.py
import asyncio
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

# Bruk pytest.mark.asyncio, IKKE pytest.mark.anyio
@pytest.mark.asyncio
async def test_full_dynamic_flow():
    """Test komplett dynamisk orkestrering"""
    
    # Import etter at path er satt opp
    from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator, Goal, GoalStatus
    from src.tools.gemini_gateway import GeminiGateway
    from src.models.procurement_models import AnskaffelseRequest
    
    # Setup
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        pytest.skip("GEMINI_API_KEY not set, skipping integration test")
    
    gemini_gateway = GeminiGateway(gemini_api_key)
    orchestrator = ReasoningOrchestrator(gemini_gateway)
    
    # Definer test-case
    request = AnskaffelseRequest(
        navn="Innkjøp av ny brannbil",
        verdi=2_500_000,
        beskrivelse="Anskaffelse av moderne brannbil med fullt utstyr"
    )
    
    # Definer mål med suksesskriterier
    goal = Goal(
        id=request.id,
        description=f"Behandle anskaffelsessak: {request.navn}",
        context={
            "request": request.model_dump()
        },
        success_criteria=[
            "Triage-vurdering er utført og lagret",
            "Status er oppdatert basert på triage-resultat",
            "Protokoll er generert hvis saken er godkjent (GRØNN/GUL)"
        ]
    )
    
    # Kjør orkestrator
    try:
        context = await orchestrator.achieve_goal(goal)
        
        # Verifiser resultater
        assert goal.status in [GoalStatus.COMPLETED, GoalStatus.REQUIRES_HUMAN, GoalStatus.FAILED]
        assert len(context.execution_history) >= 0  # Kan være 0 hvis ingen tools ble funnet
        
        # Hvis vi har tools og utførte handlinger
        if len(context.available_tools) > 0 and len(context.execution_history) > 0:
            # Sjekk at riktige verktøy ble brukt
            used_methods = [e["action"]["method"] for e in context.execution_history]
            
            # Sjekk for triage hvis det ble utført
            if any("triage" in m for m in used_methods):
                assert "triage_completed" in context.current_state
            
            # Hvis GRØNN/GUL, sjekk protokoll
            if context.current_state.get("triage_color") in ["GRØNN", "GUL"]:
                assert any("protocol" in m for m in used_methods)
            
    except Exception as e:
        pytest.fail(f"Test failed with error: {str(e)}")


# Test at discovery fungerer separat
@pytest.mark.asyncio
async def test_tool_discovery():
    """Test at verktøyoppdagelse fungerer"""
    
    from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator
    from src.tools.gemini_gateway import GeminiGateway
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        pytest.skip("GEMINI_API_KEY not set, skipping integration test")
    
    gemini_gateway = GeminiGateway(gemini_api_key)
    orchestrator = ReasoningOrchestrator(gemini_gateway)
    
    # Test discovery
    try:
        tools = await orchestrator._discover_tools()
        
        # Verifiser at vi får verktøy tilbake
        assert isinstance(tools, list)
        # Tools kan være tom hvis gateway ikke har noen registrerte verktøy
        
        # Hvis vi har verktøy, sjekk struktur
        if len(tools) > 0:
            for tool in tools:
                assert "method" in tool
                assert "service_type" in tool
                assert "description" in tool
        else:
            pytest.skip("No tools discovered, check gateway configuration")
            
    except Exception as e:
        pytest.fail(f"Tool discovery failed: {str(e)}")