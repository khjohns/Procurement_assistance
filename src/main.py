import asyncio
import os
import structlog
from dotenv import load_dotenv

from src.orchestrators.procurement_orchestrator import ProcurementOrchestrator
from src.models.procurement_models import AnskaffelseRequest, TriageResult, ProtocolResult
from src.tools.gemini_gateway import GeminiGateway
from src.specialists.triage_agent import TriageAgent
from src.specialists.protocol_generator import ProtocolGenerator # Importer den nye spesialisten

logger = structlog.get_logger()

async def main():
    load_dotenv()

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY not found in .env file.")
        return

    logger.info("Gemini API Key loaded successfully.")

    # Initialiser Gateways
    gemini_gateway = GeminiGateway(gemini_api_key)

    # Initialiser Spesialistagenter
    triage_agent = TriageAgent(gemini_gateway)
    protocol_generator = ProtocolGenerator(gemini_gateway) # Opprett instans av den nye spesialisten

    # Sett opp orkestratoren med begge spesialistene
    orkestrator = ProcurementOrchestrator(triage_agent, protocol_generator)
    logger.info("ProcurementOrchestrator initialized with all specialists.")

    # Definer test-caser
    test_cases = [
        AnskaffelseRequest(navn="Innkjøp av nye kontorstoler", verdi=750_000, beskrivelse="Standard kontorstoler til nytt kontorlandskap."),
        AnskaffelseRequest(navn="Konsulenttjenester for nytt IKT-system", verdi=1_500_000, beskrivelse="Behov for ekstern ekspertise til å integrere nytt CRM-system."),
        AnskaffelseRequest(navn="Kaffe og frukt til kontoret", verdi=150_000, beskrivelse="Løpende avtale for levering av kaffe, te og frukt til de ansatte.")
    ]

    # Kjør prosessen for hver test-case
    for i, request in enumerate(test_cases):
        logger.info(f"--- Running Test Case {i+1}: {request.navn} ---")
        
        result = await orkestrator.kjor_prosess(request)

        if isinstance(result, TriageResult):
            logger.info("Process finished after triage", 
                        request_id=request.id, 
                        outcome=result.farge)
        elif isinstance(result, ProtocolResult):
            logger.info("Process finished after protocol generation", 
                        request_id=request.id, 
                        protocol_length=len(result.protocol_text),
                        confidence=result.confidence)
        
        if i < len(test_cases) - 1:
            logger.info("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())