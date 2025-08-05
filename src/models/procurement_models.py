from pydantic import BaseModel, Field
import uuid
from enum import Enum

class TriageColor(str, Enum):
    GREEN = "GRØNN"
    YELLOW = "GUL"
    RED = "RØD"

class ProcurementRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    value: int
    description: str | None = None
    potential_supplier: str | None = None

class TriageResult(BaseModel):
    color: TriageColor
    reasoning: str
    confidence: float = Field(..., ge=0.0, le=1.0)

class ProtocolResult(BaseModel):
    """Represents the result from the ProtocolGenerator."""
    content: str
    confidence: float = Field(..., ge=0.0, le=1.0)