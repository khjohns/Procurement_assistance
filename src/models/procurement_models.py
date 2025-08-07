# src/models/procurement_models.py - OPPDATERT
from pydantic import BaseModel, Field
import uuid
from enum import Enum
from typing import Optional

class TriageColor(str, Enum):
    GREEN = "GRØNN"
    YELLOW = "GUL"
    RED = "RØD"

class ProcurementCategory(str, Enum):
    """Kategorier for anskaffelser."""
    BYGGE = "bygge"
    ANLEGG = "anlegg" 
    TJENESTE = "tjeneste"
    VARE = "vare"
    RENHOLD = "renhold"
    IT = "it"
    KONSULENT = "konsulent"

class ProcurementRequest(BaseModel):
    """
    Utvidet modell for anskaffelsesforespørsler.
    Inkluderer nå alle felter som trengs for Oslomodell-vurdering.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Navn på anskaffelsen")
    value: int = Field(..., description="Estimert verdi i NOK ekskl. mva")
    description: Optional[str] = Field(None, description="Detaljert beskrivelse")
    category: ProcurementCategory = Field(ProcurementCategory.TJENESTE, description="Type anskaffelse")
    duration_months: int = Field(0, description="Kontraktens varighet i måneder")
    potential_supplier: Optional[str] = Field(None, description="Eventuell preferert leverandør")
    
    # Nye felter for bedre Oslomodell-støtte
    includes_construction: bool = Field(False, description="Inkluderer bygge/anleggsarbeid")
    requires_security_clearance: bool = Field(False, description="Krever sikkerhetsklarering")
    international_tender: bool = Field(False, description="Internasjonal konkurranse")
    framework_agreement: bool = Field(False, description="Rammeavtale")
    estimated_suppliers: int = Field(0, description="Estimert antall tilbydere")

class TriageResult(BaseModel):
    """Resultat fra triage-vurdering."""
    color: TriageColor
    reasoning: str = Field(..., description="Begrunnelse for klassifisering")
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Nye felter for mer detaljert triage
    risk_factors: list[str] = Field(default_factory=list, description="Identifiserte risikofaktorer")
    recommendations: list[str] = Field(default_factory=list, description="Anbefalinger for videre prosess")

class ProtocolResult(BaseModel):
    """Resultat fra protokollgenerering."""
    content: str = Field(..., description="Protokollinnhold")
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Nye felter
    protocol_type: str = Field("standard", description="Type protokoll")
    sections: list[str] = Field(default_factory=list, description="Seksjoner i protokollen")

# Oslomodell-spesifikke modeller
class OslomodellRequirement(BaseModel):
    """Et enkelt Oslomodell-krav."""
    code: str = Field(..., description="Kravkode (A-V)")
    description: str = Field(..., description="Beskrivelse av kravet")
    mandatory: bool = Field(..., description="Om kravet er obligatorisk")
    category: str = Field(..., description="Kategori (seriøsitet/aktsomhet/lærling)")

class OslomodellAssessment(BaseModel):
    """Komplett Oslomodell-vurdering."""
    vurdert_risiko_for_akrim: str = Field(..., description="Vurdert risiko: høy/moderat/lav")
    påkrevde_seriøsitetskrav: list[str] = Field(..., description="Liste over påkrevde krav (A-V)")
    anbefalt_antall_underleverandørledd: int = Field(..., ge=0, le=2, description="Maks antall underleverandørledd (0-2)")
    aktsomhetsvurdering_kravsett: Optional[str] = Field(None, description="Kravsett A, B eller Ikke påkrevd")
    krav_om_lærlinger: dict = Field(..., description="Info om lærlingkrav")
    recommendations: list[str] = Field(default_factory=list, description="Anbefalinger")
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Ekstra detaljer
    identified_risk_areas: list[str] = Field(default_factory=list, description="Identifiserte risikoområder")
    applicable_instructions: list[str] = Field(default_factory=list, description="Relevante instrukspunkter")
    special_considerations: Optional[str] = Field(None, description="Spesielle hensyn")