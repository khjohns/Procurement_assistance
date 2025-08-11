# tests/conftest.py
import pytest
import asyncio
import sys
import os
from pathlib import Path

# Sett opp miljøvariabler
from dotenv import load_dotenv
load_dotenv()

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

# Global fixture for event loop
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

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