# src/specialists/triage_agent.py - Full oppdatering

import json
import structlog
from typing import Dict, Any

from src.agent_library.core import BaseSpecialistAgent
from src.agent_library.registry import register_tool
from src.agent_library.decorators import build_metadata, with_schemas
from src.models.procurement_models import ProcurementRequest, TriageResult, TriageColor

logger = structlog.get_logger()

TRIAGE_METADATA = build_metadata(
    description="Klassifiserer anskaffelse som GRØNN, GUL eller RØD",
    input_schema_class=ProcurementRequest,
    output_schema_class=TriageResult
)

TRIAGE_SYSTEM_PROMPT = """
Du er ekspert på norsk anskaffelsesregelverk.
Vurder denne anskaffelsen og klassifiser som GRØNN, GUL eller RØD.

KRITERIER:
- GRØNN: < 500k NOK, lav kompleksitet, ingen risiko
- GUL: 500k-1.3M NOK eller moderat kompleksitet
- RØD: > 1.3M NOK eller høy risiko (GDPR, sikkerhet, etc)

Svar KUN med JSON: {"color": "GRØNN/GUL/RØD", "reasoning": "...", "confidence": 0.0-1.0}
"""

# ENDRE: Oppdatert registrering med llm_gateway
@register_tool(
    name="agent.run_triage",
    service_type="specialist_agent",
    metadata=TRIAGE_METADATA,
    dependencies=["llm_gateway"]  # Bruker llm_gateway
)
@with_schemas(input_schema=ProcurementRequest, output_schema=TriageResult)
class TriageAgent(BaseSpecialistAgent):
    """Enhanced triage agent using purpose-optimized LLM."""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute triage with enhanced LLM."""
        procurement_data = params.get("procurement", params)
        
        # OPTIMALISERING: Rask vurdering for lave verdier
        value = procurement_data.get("value", 0)
        if value < 100_000:
            # Bruk billigste modell for enkle saker
            return await self._quick_triage(procurement_data)
        
        # Bruk generate_structured med riktig purpose (uten try/except)
        result = await self.llm_gateway.generate_structured(
            prompt=f"""
{TRIAGE_SYSTEM_PROMPT}

Anskaffelse:
- Navn: {procurement_data.get('name')}
- Verdi: {procurement_data.get('value')} NOK
- Beskrivelse: {procurement_data.get('description')}
""",
            response_schema={
                "type": "object",
                "properties": {
                    "color": {"type": "string", "enum": ["GRØNN", "GUL", "RØD"]},
                    "reasoning": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["color", "reasoning", "confidence"]
            },
            purpose="fast_evaluation",  # Triage er rask evaluering
            temperature=0.3,
            thinking_budget=8192  # Begrenset thinking for hastighet
        )
        
        logger.info("Triage completed", 
                   color=result["color"],
                   confidence=result["confidence"])
        
        return result
    
    async def _quick_triage(self, procurement_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ultra-rask triage for lave verdier med billigste modell."""
        # ENDRING: Gi et mye tydeligere prompt for å sikre korrekt format
        quick_prompt = f"""
Vurder denne lav-verdi anskaffelsen og klassifiser den. Nesten alltid GRØNN.
Svar KUN med JSON: {{"color": "GRØNN", "reasoning": "...", "confidence": 0.95}}

Anskaffelse:
- Navn: {procurement_data.get('name')}
- Verdi: {procurement_data.get('value')} NOK
"""
        
        result = await self.llm_gateway.generate_structured(
            prompt=quick_prompt,
            response_schema=TriageResult.model_json_schema(),
            purpose="cost_efficient",
            temperature=0.1
        )
        
        # Sikre at vi har standardverdier hvis modellen er usikker
        return {
            "color": result.get("color", "GRØNN"),
            "reasoning": result.get("reasoning", "Lav verdi, standard prosedyre."),
            "confidence": result.get("confidence", 0.95)
        }
        
