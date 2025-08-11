# src/specialists/triage_agent.py

import json
import structlog
from typing import Dict, Any, List
from pydantic import BaseModel

from src.agent_library.core import BaseSpecialistAgent
from src.agent_library.registry import register_tool
from src.agent_library.decorators import build_metadata, with_schemas
from src.models.procurement_models import ProcurementRequest, TriageResult, TriageColor

logger = structlog.get_logger()

# ENDRING 1: Modellen er nå fullt synkronisert med TriageResult
class LLM_TriageResponse(BaseModel):
    """Definerer KUN de feltene vi forventer at LLM skal generere."""
    color: TriageColor
    reasoning: str
    confidence: float
    risk_factors: List[str] = []
    mitigation_measures: List[str] = [] # Navneendring fra recommendations
    requires_special_attention: bool = False
    escalation_recommended: bool = False

TRIAGE_METADATA = build_metadata(
    description="Klassifiserer anskaffelse som GRØNN, GUL eller RØD med risikovurdering.",
    input_schema_class=ProcurementRequest,
    output_schema_class=TriageResult
)

# ENDRING 2: Prompten er oppdatert for å be om rikere informasjon
TRIAGE_SYSTEM_PROMPT = """
Du er ekspert på norsk anskaffelsesregelverk.
Vurder anskaffelsen og klassifiser som GRØNN, GUL eller RØD.
Identifiser også risikofaktorer og foreslå tiltak.

KRITERIER:
- GRØNN: < 500k NOK, lav kompleksitet, ingen risiko.
- GUL: 500k-1.3M NOK eller moderat kompleksitet/risiko.
- RØD: > 1.3M NOK eller høy risiko (GDPR, sikkerhet, etc).

Svar KUN med JSON som følger dette formatet:
{
    "color": "GRØNN/GUL/RØD",
    "reasoning": "Din begrunnelse...",
    "confidence": 0.0-1.0,
    "risk_factors": ["En liste med risikofaktorer..."],
    "mitigation_measures": ["En liste med foreslåtte tiltak..."],
    "requires_special_attention": true/false,
    "escalation_recommended": true/false
}
"""

@register_tool(
    name="agent.run_triage",
    service_type="specialist_agent",
    metadata=TRIAGE_METADATA,
    dependencies=["llm_gateway"],
    save_method="database.save_triage_result"
)
@with_schemas(input_schema=ProcurementRequest, output_schema=TriageResult)
class TriageAgent(BaseSpecialistAgent):
    """Enhanced triage agent using purpose-optimized LLM and Pydantic validation."""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute triage with full validation."""
        try:
            procurement = ProcurementRequest.model_validate(params.get("procurement", params))
        except Exception as e:
            logger.error("Failed to validate triage input", error=str(e))
            raise ValueError(f"Invalid procurement data for TriageAgent: {e}")

        prompt = f"""
{TRIAGE_SYSTEM_PROMPT}

Anskaffelse til vurdering:
- Navn: {procurement.name}
- Verdi: {procurement.value} NOK
- Beskrivelse: {procurement.description}
- Kategori: {procurement.category.value}
"""
        
        llm_response_dict = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema=LLM_TriageResponse.model_json_schema(),
            purpose="fast_evaluation",
            temperature=0.3
        )
        
        final_data = {
            **llm_response_dict,
            "procurement_id": procurement.id,
            "procurement_name": procurement.name
        }
        
        try:
            final_result = TriageResult.model_validate(final_data)
        except Exception as e:
            logger.error("Failed to validate final combined data for Triage", error=str(e), final_data=final_data)
            return self._create_default_triage(procurement).model_dump()
            
        logger.info("Triage completed and validated", 
                    color=final_result.color.value, 
                    confidence=final_result.confidence)
        
        return final_result.model_dump()

    def _create_default_triage(self, procurement: ProcurementRequest) -> TriageResult:
        """Creates a safe, default triage result if generation/validation fails."""
        color = TriageColor.YELLOW
        reason = "Automatisk klassifisert på grunn av usikkert svar fra AI-modell."
        
        if procurement.value < 500000:
            color = TriageColor.GREEN
            reason = "Automatisk klassifisert som GRØNN pga. lav verdi."
        elif procurement.value > 1300000:
            color = TriageColor.RED
            reason = "Automatisk klassifisert som RØD pga. høy verdi."
            
        # ENDRING 3: Standard-svaret er nå komplett
        return TriageResult(
            procurement_id=procurement.id,
            procurement_name=procurement.name,
            color=color,
            reasoning=reason,
            confidence=0.5,
            risk_factors=["AI-vurdering feilet"],
            mitigation_measures=["Manuell gjennomgang påkrevd"],
            requires_special_attention=True,
            escalation_recommended=False
        )