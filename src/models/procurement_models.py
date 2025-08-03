from pydantic import BaseModel, Field
import uuid

class AnskaffelseRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    navn: str
    verdi: int
    beskrivelse: str | None = None # Lagt til for protokoll-generering
    potensiell_leverandoer: str | None = None # Lagt til for protokoll-generering

class TriageResult(BaseModel):
    farge: str
    begrunnelse: str
    confidence: float = Field(..., ge=0.0, le=1.0)

class ProtocolResult(BaseModel):
    """Representerer resultatet fra ProtocolGenerator."""
    protocol_text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
