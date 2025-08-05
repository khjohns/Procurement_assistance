from src.models.procurement_models import ProcurementRequest, ProtocolResult
from src.tools.gemini_gateway import GeminiGateway
import structlog

logger = structlog.get_logger()

PROTOCOL_SYSTEM_PROMPT = """
Du er en ekspert på offentlige anskaffelser og din oppgave er å skrive et utkast til en anskaffelsesprotokoll.
Basert på informasjonen i en `ProcurementRequest`, skal du generere en formell protokoll.
Protokollen skal være nøytral, faktabasert og følge en standard mal.
"""

class ProtocolGenerator:
    """
    Level 3 Specialist Agent: Generates a draft for a procurement protocol.
    """
    def __init__(self, llm_gateway: GeminiGateway):
        self.llm_gateway = llm_gateway
        logger.info("ProtocolGenerator initialized", llm_gateway=llm_gateway)

    async def generate_protocol(self, request: ProcurementRequest) -> ProtocolResult:
        """
        Generates a protocol draft based on a procurement request.

        Args:
            request: The procurement request.

        Returns:
            A ProtocolResult object containing the protocol draft.
        """
        logger.info("Generating protocol for request", request_id=request.id)

        user_prompt = f"""
        Procurement ID: {request.id}
        Title: {request.name}
        Description: {request.description}
        Estimated Value: {request.value} NOK
        Potential Supplier: {request.potential_supplier}

        Generate a protocol draft based on this data.
        """

        full_prompt = f"{PROTOCOL_SYSTEM_PROMPT}\n\n{user_prompt}"

        request_data = request.model_dump()

        generated_text = await self.llm_gateway.generate(
            prompt=full_prompt,
            data=request_data
        )

        protocol_result = ProtocolResult(
            content=generated_text,
            confidence=0.9  # Placeholder value
        )

        logger.info("Protocol generated", request_id=request.id, confidence=protocol_result.confidence)
        return protocol_result