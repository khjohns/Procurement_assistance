# tests/conftest.py

import pytest
import os
from dotenv import load_dotenv

# Importer klassene dine (juster stiene etter din prosjektstruktur)
from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator
from src.tools.llm_gateway import LLMGateway
from src.tools.embedding_gateway import EmbeddingGateway
# Antar at TestReporter-klassen er i testfilen, så vi importerer den derfra
from tests.test_reasoning_orchestrator_comprehensive import TestReporter


# KRITISK: Importer alle agent-moduler for å sikre at de blir registrert i TOOL_REGISTRY
# Pythons import-system kjører koden i disse filene, inkludert @register_tool-dekoratorene.
# Uten disse importene vil orkestratoren ikke vite om noen spesialistagenter.
import src.specialists.triage_agent
import src.specialists.oslomodel_agent
import src.specialists.environmental_agent
# Legg til flere agenter her etter hvert som de lages

# Konfigurer pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# Deaktiver anyio backends vi ikke bruker
def pytest_configure(config):
    """Konfigurer pytest"""
    # Bare bruk asyncio, ikke trio
    config.option.asyncio_mode = "auto"

# Marker for å hoppe over trio-tester
def pytest_collection_modifyitems(config, items):
    """Modifier test collection"""
    for item in items:
        # Skip trio variants av asyncio tester
        if "[trio]" in item.name:
            item.add_marker(pytest.mark.skip(reason="Trio not installed"))

# Denne fixturen kjører én gang for hele test-økten
@pytest.fixture(scope="session")
def reporter():
    """
    En fixture som oppretter og gir tilgang til én enkelt TestReporter-instans
    for hele testkjøringen.
    """
    # Lag en instans av din TestReporter
    reporter_instance = TestReporter()
    
    # 'yield' sender instansen til testene
    yield reporter_instance
    
    # Koden etter yield kjøres etter at alle testene er ferdige
    print("\n--- Generating Final Test Report ---")
    reporter_instance.print_summary()


@pytest.fixture(scope="session")
def orchestrator():
    """
    En fixture som setter opp og returnerer en ReasoningOrchestrator-instans.
    Kjører kun én gang for hele test-økten.
    """
    llm_gateway = LLMGateway()
   
    orchestrator_instance = ReasoningOrchestrator(
        llm_gateway=llm_gateway,
    )
    
    print("✅ Orchestrator is ready.")
    return orchestrator_instance

# Fixture for å sjekke at gateway kjører
@pytest.fixture
async def ensure_gateway_running():
    """Sjekker at gateway kjører før tester"""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code != 200:
                pytest.skip("Gateway is not healthy")
    except Exception:
        pytest.skip("Gateway is not running on http://localhost:8000")