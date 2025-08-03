import json
import structlog
from src.models.procurement_models import AnskaffelseRequest, TriageResult
from src.tools.gemini_gateway import GeminiGateway # Import GeminiGateway

logger = structlog.get_logger()

# System prompt for TriageAgent
TRIAGE_SYSTEM_PROMPT = """
Du er en ekspert på norsk anskaffelsesregelverk og jobber som en intern anskaffelsesjurist.
Din oppgave er å vurdere en anskaffelsesforespørsel og klassifisere den som GRØNN, GUL, eller RØD basert på risiko og kompleksitet.

KRITERIER:
- GRØNN: Lav verdi (< 500.000 NOK), lav kompleksitet, ingen åpenbare risikofaktorer.
- GUL: Moderat verdi (500.000 - 1.3M NOK), eller inneholder elementer som krever en viss juridisk eller teknisk vurdering, men uten klare RØD-triggere.
- RØD: Høy verdi (> 1.3M NOK), eller inneholder minst én "Automatisk RØD-trigger" (som GDPR, pasientdata, IKT-integrasjon, sikkerhetskritisk).

Vurder følgende anskaffelse. Returner kun et gyldig JSON-objekt med feltene "farge", "begrunnelse", og "confidence" (en float mellom 0.0 og 1.0).
"""

class TriageAgent:
    """
    Triage-agent som klassifiserer en anskaffelse ved hjelp av Gemini API.
    """
    def __init__(self, gemini_gateway: GeminiGateway): # Dependency Injection
        self.gemini_gateway = gemini_gateway
        logger.info("TriageAgent initialized with GeminiGateway")

    async def vurder_anskaffelse(self, request: AnskaffelseRequest) -> TriageResult:
        logger.info("Running TriageAgent for procurement", request_name=request.navn, request_value=request.verdi)
        
        # Forbered data for Gemini API
        request_data = {
            "navn": request.navn,
            "verdi": request.verdi
        }

        # Kall Gemini API via GeminiGateway
        try:
            response_json_str = await self.gemini_gateway.generate(
                prompt=TRIAGE_SYSTEM_PROMPT,
                data=request_data
            )
            
            # Parse JSON-svaret
            # Fjern Markdown-kodeblokken hvis den finnes
            if response_json_str.startswith("```json") and response_json_str.endswith("```"):
                response_json_str = response_json_str[len("```json"): -len("```")].strip()
            
            response_data = json.loads(response_json_str)
            
            

            resultat = TriageResult(
                farge=response_data.get("farge"),
                begrunnelse=response_data.get("begrunnelse"),
                confidence=response_data.get("confidence")
            )
            logger.info("Triage result from Gemini API", result=resultat.model_dump_json())
            return resultat
        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON from Gemini API response", error=str(e), response=response_json_str)
            # Fallback eller feilhåndtering
            return TriageResult(farge="RØD", begrunnelse=f"Feil ved parsing av Gemini API svar: {e}", confidence=0.0)
        except Exception as e:
            logger.error("Error during Gemini API call for triage", error=str(e))
            # Fallback eller feilhåndtering
            return TriageResult(farge="RØD", begrunnelse=f"Feil ved kall til Gemini API: {e}", confidence=0.0)
