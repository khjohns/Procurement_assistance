# tests/standalone/test_triage_agent_isolated.py
import asyncio
import os
import json
from dotenv import load_dotenv

# --- Importer nødvendige komponenter fra prosjektet ditt ---
from src.tools.enhanced_llm_gateway import LLMGateway
from src.specialists.triage_agent import TriageAgent
from src.models.procurement_models_refactored import TriageResult

# --- Test-funksjonalitet ---

async def run_agent_test(agent: TriageAgent, test_name: str, procurement_data: dict):
    """Kjører en enkelt test mot agenten og printer resultatet."""
    print(f"\n--- 🧪 Kjører test: {test_name} ---")
    
    # Agentens `execute`-metode forventer en 'procurement'-nøkkel i parameterne
    params = {"procurement": procurement_data}
    
    try:
        print(f"Input til agent: {json.dumps(procurement_data, indent=2, ensure_ascii=False)}")
        
        # Kjør selve agenten
        result_dict = await agent.execute(params)
        
        print("\n✅ Agenten kjørte vellykket!")
        print("Rått resultat fra agent:")
        print(json.dumps(result_dict, indent=2, ensure_ascii=False))
        
        # Verifiser at resultatet samsvarer med Pydantic-modellen
        try:
            TriageResult.model_validate(result_dict)
            print("\n✅ Pydantic-validering: Suksess! Resultatet følger TriageResult-modellen.")
        except Exception as pydantic_error:
            print(f"\n❌ Pydantic-validering: FEIL! {pydantic_error}")

    except Exception as e:
        print(f"\n❌ Testen feilet med en exception: {e}")
        
    print("-" * (len(test_name) + 20))


async def main():
    """Hovedfunksjon for å sette opp og kjøre testene."""
    print("=============================================")
    print("  Isolert test av TriageAgent 🕵️")
    print("=============================================")
    
    # --- Oppsett ---
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Fant ikke GEMINI_API_KEY. Sjekk din .env-fil.")
        return
        
    print("1. Setter opp LLM Gateway...")
    llm_gateway = LLMGateway()
    
    print("2. Initialiserer TriageAgent...")
    triage_agent = TriageAgent(llm_gateway)
    
    # --- Test-scenarioer ---
    
    # Scenario 1: Enkel, lav-verdi anskaffelse (forventer GRØNN)
    test_data_green = {
        "id": "test-green-001",
        "name": "Kaffe og te til kontoret",
        "value": 50000,
        "description": "Årlig innkjøp av kaffe, te og melk.",
        "category": "vare"
    }

    # Scenario 2: Høy-verdi IT-system (forventer RØD)
    test_data_red = {
        "id": "test-red-001",
        "name": "Nytt HR-system med sensitive data",
        "value": 2500000,
        "description": "Implementering av skybasert HR-system for alle ansatte.",
        "category": "it"
    }
    
    # --- Kjøring ---
    await run_agent_test(triage_agent, "GRØNN Scenario", test_data_green)
    await run_agent_test(triage_agent, "RØD Scenario", test_data_red)


if __name__ == "__main__":
    asyncio.run(main())