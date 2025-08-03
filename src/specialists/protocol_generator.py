from src.models.procurement_models import AnskaffelseRequest, ProtocolResult
from src.tools.gemini_gateway import GeminiGateway
import structlog

logger = structlog.get_logger()

PROTOCOL_SYSTEM_PROMPT = """
Du er en ekspert på offentlige anskaffelser og din oppgave er å skrive et utkast til en anskaffelsesprotokoll.
Basert på informasjonen i en `AnskaffelseRequest`, skal du generere en formell protokoll.
Protokollen skal være nøytral, faktabasert og følge en standard mal.
"""

class ProtocolGenerator:
    """
    Nivå 3 Spesialistagent: Genererer et utkast til en anskaffelsesprotokoll.
    """
    def __init__(self, llm_gateway: GeminiGateway):
        self.llm_gateway = llm_gateway
        logger.info("ProtocolGenerator initialized", llm_gateway=llm_gateway)

    async def generate_protocol(self, request: AnskaffelseRequest) -> ProtocolResult:
        """
        Genererer protokollutkast basert på en anskaffelsesforespørsel.

        Args:
            request: Anskaffelsesforespørselen.

        Returns:
            Et ProtocolResult-objekt som inneholder protokollutkastet.
        """
        logger.info("Generating protocol for request", request_id=request.id)

        user_prompt = f"""
        Anskaffelses-ID: {request.id}
        Tittel: {request.navn}
        Beskrivelse: {request.beskrivelse}
        Estimat: {request.verdi} NOK
        Leverandør: {request.potensiell_leverandoer}

        Generer et protokollutkast basert på disse dataene.
        """

        full_prompt = f"{PROTOCOL_SYSTEM_PROMPT}\n\n{user_prompt}"

        # Konverter request-objektet til en dictionary for gatewayen
        request_data = request.model_dump()

        generated_text = await self.llm_gateway.generate(
            prompt=full_prompt,
            data=request_data
        )

        protocol_result = ProtocolResult(
            protocol_text=generated_text,
            confidence=0.9  # Midlertidig hardkodet verdi
        )

        logger.info("Protocol generated", request_id=request.id, confidence=protocol_result.confidence)
        return protocol_result
