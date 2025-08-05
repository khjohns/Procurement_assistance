import json
import structlog
from src.models.procurement_models import ProcurementRequest, TriageResult, TriageColor
from src.tools.gemini_gateway import GeminiGateway

logger = structlog.get_logger()

# System prompt for TriageAgent, updated to request English keys
TRIAGE_SYSTEM_PROMPT = """
Du er en ekspert på norsk anskaffelsesregelverk og jobber som en intern anskaffelsesjurist.
Din oppgave er å vurdere en anskaffelsesforespørsel og klassifisere den som GRØNN, GUL, eller RØD basert på risiko og kompleksitet.

KRITERIER:
- GRØNN: Lav verdi (< 500.000 NOK), lav kompleksitet, ingen åpenbare risikofaktorer.
- GUL: Moderat verdi (500.000 - 1.3M NOK), eller inneholder elementer som krever en viss juridisk eller teknisk vurdering, men uten klare RØD-triggere.
- RØD: Høy verdi (> 1.3M NOK), eller inneholder minst én "Automatisk RØD-trigger" (som GDPR, pasientdata, IKT-integrasjon, sikkerhetskritisk).

Vurder følgende anskaffelse. Returner kun et gyldig JSON-objekt med feltene "color", "reasoning", og "confidence" (en float mellom 0.0 og 1.0).
"""

class TriageAgent:
    """
    Triage agent that classifies a procurement using the Gemini API.
    """
    def __init__(self, gemini_gateway: GeminiGateway):
        self.gemini_gateway = gemini_gateway
        logger.info("TriageAgent initialized with GeminiGateway")

    async def assess_procurement(self, request: ProcurementRequest) -> TriageResult:
        logger.info("Running TriageAgent for procurement", request_name=request.name, request_value=request.value)
        
        request_data = {
            "name": request.name,
            "value": request.value,
            "description": request.description
        }

        try:
            response_json_str = await self.gemini_gateway.generate(
                prompt=TRIAGE_SYSTEM_PROMPT,
                data=request_data,
                response_mime_type="application/json"
            )
            
            response_data = json.loads(response_json_str)

            result = TriageResult(
                color=response_data.get("color"),
                reasoning=response_data.get("reasoning"),
                confidence=response_data.get("confidence")
            )
            logger.info("Triage result from Gemini API", result=result.model_dump_json())
            return result
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to decode JSON from Gemini API response", error=str(e), response=response_json_str)
            return TriageResult(color=TriageColor.RED, reasoning=f"Error parsing Gemini API response: {e}", confidence=0.0)
        except Exception as e:
            logger.error("Error during Gemini API call for triage", error=str(e))
            return TriageResult(color=TriageColor.RED, reasoning=f"Error calling Gemini API: {e}", confidence=0.0)