# src/models/llm_models.py

from pydantic import BaseModel, Field
from .enums import RiskLevel

class LLMRiskAssessmentOutput(BaseModel):
    """
    Definerer den forventede strukturen på svaret fra en LLM
    som utfører en risikovurdering.
    """
    risk_level: RiskLevel = Field(..., description="Det klassifiserte risikonivået (lav, moderat, eller høy).")
    justification: str = Field(..., description="En kort, faktabasert begrunnelse for klassifiseringen.")