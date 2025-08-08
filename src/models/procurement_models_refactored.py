# src/models/procurement_models.py - REFACTORED VERSION
"""
Sentraliserte, standardiserte datamodeller for AI Agent SDK.
Erstatter fragmenterte og dupliserte modeller med en enhetlig arkitektur.
"""
from pydantic import BaseModel, Field, field_validator
import uuid
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime

# ========================================
# ENUMS - Grunnleggende kategorier
# ========================================

class ProcurementCategory(str, Enum):
    """Kategorier for anskaffelser."""
    BYGGE = "bygge"
    ANLEGG = "anlegg"
    TJENESTE = "tjeneste"
    VARE = "vare"
    RENHOLD = "renhold"
    IT = "it"
    KONSULENT = "konsulent"

class TransportType(str, Enum):
    """Type transport i anskaffelse."""
    MASSETRANSPORT = "massetransport"
    PERSONTRANSPORT = "persontransport"
    VARETRANSPORT = "varetransport"
    ANLEGGSTRANSPORT = "anleggstransport"
    NONE = "ingen"

class EnvironmentalRiskLevel(str, Enum):
    """Miljørisiko-nivåer."""
    LOW = "lav"
    MEDIUM = "middels"
    HIGH = "høy"

class TriageColor(str, Enum):
    """Triage klassifisering."""
    GREEN = "GRØNN"
    YELLOW = "GUL"
    RED = "RØD"

class RequirementSource(str, Enum):
    """Kilden til et krav."""
    OSLOMODELLEN = "oslomodellen"
    MILJOKRAV = "miljøkrav"
    ANSKAFFELSESFORSKRIFT = "anskaffelsesforskrift"
    OTHER = "annet"

class RequirementCategory(str, Enum):
    """Kategori for krav."""
    SERIOSITET = "seriøsitet"
    AKTSOMHET = "aktsomhet"
    LARLINGER = "lærlinger"
    MILJO = "miljø"
    KLIMA = "klima"
    TRANSPORT = "transport"
    DOKUMENTASJON = "dokumentasjon"
    OTHER = "annet"

# ========================================
# ENHETLIG INPUT MODEL
# ========================================

class ProcurementRequest(BaseModel):
    """
    Komplett, enhetlig datamodell for en anskaffelsesforespørsel.
    Dekker alle behov for Oslomodell, Miljøkrav og andre vurderinger.
    """
    # Kjerneinformasjon
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Navn på anskaffelsen")
    value: int = Field(..., description="Estimert verdi i NOK ekskl. mva", ge=0)
    description: Optional[str] = Field(None, description="Detaljert beskrivelse")
    category: ProcurementCategory = Field(..., description="Type anskaffelse")
    duration_months: int = Field(0, description="Kontraktens varighet i måneder", ge=0)
    
    # Leverandør og marked
    potential_supplier: Optional[str] = Field(None, description="Eventuell preferert leverandør")
    known_suppliers_count: int = Field(0, description="Antall kjente leverandører", ge=0)
    market_dialogue_completed: bool = Field(False, description="Om markedsdialog er gjennomført")
    framework_agreement: bool = Field(False, description="Om det er en rammeavtale")
    
    # Konstruksjon og anlegg
    includes_construction: bool = Field(False, description="Inkluderer bygge/anleggsarbeid")
    construction_site_size: Optional[int] = Field(None, description="Størrelse på byggeplass i m2", ge=0)
    involves_demolition: bool = Field(False, description="Inkluderer rivningsarbeid")
    involves_earthworks: bool = Field(False, description="Inkluderer grunnarbeid")
    
    # Transport
    involves_transport: bool = Field(False, description="Innebærer anskaffelsen transport")
    transport_type: TransportType = Field(TransportType.NONE, description="Type transport")
    estimated_transport_volume: Optional[int] = Field(None, description="Estimert transportvolum i tonn/turer", ge=0)
    
    # Miljø og energi
    energy_requirement_kwh: Optional[int] = Field(None, description="Estimert energibehov i kWh", ge=0)
    requires_heating: bool = Field(False, description="Krever oppvarming/kjøling")
    waste_management_included: bool = Field(False, description="Inkluderer avfallshåndtering")
    
    # Sikkerhet og internasjonalt
    requires_security_clearance: bool = Field(False, description="Krever sikkerhetsklarering")
    international_tender: bool = Field(False, description="Internasjonal konkurranse")
    
    # Administrative detaljer
    estimated_suppliers: int = Field(0, description="Estimert antall tilbydere", ge=0)
    innovation_potential: bool = Field(False, description="Potensial for innovasjon")
    
    @field_validator('value')
    def validate_value(cls, v):
        if v < 0:
            raise ValueError("Procurement value cannot be negative")
        return v

# ========================================
# GENERISK KRAV-MODELL
# ========================================

class Requirement(BaseModel):
    """
    Generisk modell for et enkelt krav fra ethvert regelverk.
    Rik, selvforklarende datastruktur.
    """
    code: str = Field(..., description="Unik kravkode, f.eks. 'A', 'MK-01'")
    name: str = Field(..., description="Kort navn på kravet")
    description: str = Field(..., description="Detaljert beskrivelse")
    mandatory: bool = Field(..., description="Om kravet er obligatorisk")
    source: RequirementSource = Field(..., description="Hvilket regelverk kravet kommer fra")
    category: RequirementCategory = Field(..., description="Kategori for kravet")
    
    # Valgfrie metadata
    legal_reference: Optional[str] = Field(None, description="Lovhenvisning")
    deadline: Optional[str] = Field(None, description="Frist for implementering")
    exceptions_allowed: bool = Field(False, description="Om unntak er tillatt")
    verification_method: Optional[str] = Field(None, description="Hvordan kravet verifiseres")

class RequirementException(BaseModel):
    """Modell for unntak fra krav."""
    requirement_code: str = Field(..., description="Kravkode det gis unntak fra")
    reason: str = Field(..., description="Begrunnelse for unntak")
    alternative_measures: List[str] = Field(default_factory=list, description="Alternative tiltak")
    documentation_required: bool = Field(True, description="Om dokumentasjon kreves")
    approved_by: Optional[str] = Field(None, description="Hvem som godkjente unntaket")
    approval_date: Optional[str] = Field(None, description="Dato for godkjenning")

# ========================================
# STANDARDISERT OUTPUT BASE
# ========================================

class BaseAssessmentResult(BaseModel):
    """
    Baseklasse for alle vurderingsresultater.
    Sikrer konsistent metadata på tvers av alle agenter.
    """
    procurement_id: str = Field(..., description="ID for vurdert anskaffelse")
    procurement_name: str = Field(..., description="Navn på anskaffelsen")
    
    # Felles metadata
    confidence: float = Field(..., ge=0.0, le=1.0, description="Modellens sikkerhet")
    assessment_date: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Dato for vurdering"
    )
    assessed_by: str = Field(..., description="Agent som utførte vurderingen")
    
    # Felles resultater
    recommendations: List[str] = Field(default_factory=list, description="Anbefalinger")
    warnings: List[str] = Field(default_factory=list, description="Advarsler")
    information_gaps: List[str] = Field(default_factory=list, description="Manglende informasjon")
    
    # Referanser og kilder
    context_documents_used: List[str] = Field(default_factory=list, description="Dokumenter brukt i vurdering")
    confidence_factors: Dict[str, float] = Field(default_factory=dict, description="Faktorer som påvirker sikkerhet")

# ========================================
# OSLOMODELL-SPESIFIKKE MODELLER
# ========================================

class ApprenticshipRequirement(BaseModel):
    """Strukturert modell for lærlingkrav."""
    required: bool = Field(..., description="Om lærlinger er påkrevd")
    reason: str = Field(..., description="Begrunnelse for kravet")
    minimum_count: int = Field(0, description="Minimum antall lærlinger", ge=0)
    applicable_trades: List[str] = Field(default_factory=list, description="Relevante fagområder")
    threshold_exceeded: bool = Field(False, description="Om terskelverdi er overskredet")

class OslomodellAssessmentResult(BaseAssessmentResult):
    """
    Resultat fra Oslomodell-vurdering med rike, strukturerte data.
    """
    assessed_by: str = Field(default="oslomodell_agent")
    
    # Risikovurdering
    risk_assessment_akrim: str = Field(..., description="Risiko for arbeidslivskriminalitet: høy/moderat/lav")
    risk_assessment_social_dumping: str = Field(..., description="Risiko for sosial dumping: høy/moderat/lav")
    
    # Krav med full metadata
    required_requirements: List[Requirement] = Field(
        default_factory=list, 
        description="Komplette krav som gjelder"
    )
    
    # Strukturerte sub-vurderinger
    subcontractor_levels: int = Field(..., ge=0, le=2, description="Maks antall underleverandørledd")
    subcontractor_justification: str = Field(..., description="Begrunnelse for antall ledd")
    
    apprenticeship_requirement: ApprenticshipRequirement = Field(..., description="Strukturert lærlingkrav")
    
    due_diligence_requirement: Optional[str] = Field(None, description="Aktsomhetsvurdering kravsett: A/B/Ikke påkrevd")
    
    # Spesifikke Oslomodell-metadata
    applicable_instruction_points: List[str] = Field(
        default_factory=list,
        description="Relevante punkter fra instruksen"
    )
    
    identified_risk_areas: List[str] = Field(
        default_factory=list,
        description="Identifiserte risikoområder"
    )

# ========================================
# MILJØKRAV-SPESIFIKKE MODELLER
# ========================================

class TransportRequirement(BaseModel):
    """Strukturert modell for transportkrav."""
    type: TransportType = Field(..., description="Type transport")
    zero_emission_required: bool = Field(..., description="Om nullutslipp kreves")
    biofuel_alternative: bool = Field(..., description="Om biodrivstoff er alternativ")
    deadline: Optional[str] = Field(None, description="Frist for implementering")
    incentive_applicable: bool = Field(..., description="Om insentiver gjelder")

class MiljokravAssessmentResult(BaseAssessmentResult):
    """
    Resultat fra Miljøkrav-vurdering med strukturerte miljødata.
    """
    assessed_by: str = Field(default="miljokrav_agent")
    
    # Overordnet miljøvurdering
    environmental_risk: EnvironmentalRiskLevel = Field(..., description="Samlet miljørisiko")
    climate_impact_assessed: bool = Field(True, description="Om klimapåvirkning er vurdert")
    
    # Krav med full metadata
    applied_requirements: List[Requirement] = Field(
        default_factory=list,
        description="Miljøkrav som gjelder"
    )
    
    # Strukturerte transport-krav
    transport_requirements: List[TransportRequirement] = Field(
        default_factory=list,
        description="Spesifikke transportkrav"
    )
    
    # Unntak og minimumskrav
    exceptions_recommended: List[RequirementException] = Field(
        default_factory=list,
        description="Anbefalte unntak med begrunnelse"
    )
    
    minimum_biofuel_required: bool = Field(False, description="Om minimumskrav biodrivstoff gjelder")
    
    # Viktige frister og milepæler
    important_deadlines: Dict[str, str] = Field(
        default_factory=dict,
        description="Viktige frister (nøkkel: beskrivelse, verdi: dato)"
    )
    
    # Dokumentasjon og oppfølging
    documentation_requirements: List[str] = Field(
        default_factory=list,
        description="Krav til dokumentasjon"
    )
    
    follow_up_points: List[str] = Field(
        default_factory=list,
        description="Punkter for kontraktsoppfølging"
    )
    
    market_dialogue_recommended: bool = Field(False, description="Om markedsdialog anbefales")
    
    # Tildelingskriterier
    award_criteria_recommended: List[str] = Field(
        default_factory=list,
        description="Anbefalte tildelingskriterier"
    )

# ========================================
# TRIAGE-SPESIFIKKE MODELLER
# ========================================

class TriageResult(BaseAssessmentResult):
    """
    Resultat fra triage-vurdering.
    """
    assessed_by: str = Field(default="triage_agent")
    
    color: TriageColor = Field(..., description="Triage-klassifisering")
    reasoning: str = Field(..., description="Begrunnelse for klassifisering")
    
    risk_factors: List[str] = Field(default_factory=list, description="Identifiserte risikofaktorer")
    mitigation_measures: List[str] = Field(default_factory=list, description="Foreslåtte risikoreduserende tiltak")
    
    requires_special_attention: bool = Field(False, description="Krever spesiell oppmerksomhet")
    escalation_recommended: bool = Field(False, description="Anbefaler eskalering")

# ========================================
# PROTOKOLL-MODELLER
# ========================================

class ProtocolResult(BaseAssessmentResult):
    """
    Resultat fra protokollgenerering.
    """
    assessed_by: str = Field(default="protocol_generator")
    
    content: str = Field(..., description="Protokollinnhold")
    protocol_type: str = Field("standard", description="Type protokoll")
    
    sections: List[str] = Field(default_factory=list, description="Seksjoner i protokollen")
    
    # Referanser til andre vurderinger
    based_on_assessments: List[str] = Field(
        default_factory=list,
        description="Liste over assessment-IDer protokollen baserer seg på"
    )
    
    approval_status: str = Field("draft", description="Godkjenningsstatus: draft/review/approved")
    version: str = Field("1.0", description="Versjonsnummer")

# ========================================
# AGGREGERTE RESULTATER
# ========================================

class ComprehensiveAssessment(BaseModel):
    """
    Samlet resultat fra alle vurderinger for en anskaffelse.
    """
    procurement_request: ProcurementRequest
    
    oslomodell_result: Optional[OslomodellAssessmentResult] = None
    miljokrav_result: Optional[MiljokravAssessmentResult] = None
    triage_result: Optional[TriageResult] = None
    protocol_result: Optional[ProtocolResult] = None
    
    overall_recommendation: str = Field(..., description="Samlet anbefaling")
    total_requirements_count: int = Field(0, description="Totalt antall krav", ge=0)
    
    compliance_score: float = Field(0.0, ge=0.0, le=1.0, description="Samlet etterlevelsesscore")
    
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Tidspunkt for samlet vurdering"
    )
    
    def aggregate_requirements(self) -> List[Requirement]:
        """Samler alle krav fra ulike vurderinger."""
        all_requirements = []
        
        if self.oslomodell_result:
            all_requirements.extend(self.oslomodell_result.required_requirements)
        
        if self.miljokrav_result:
            all_requirements.extend(self.miljokrav_result.applied_requirements)
        
        # Dedupliser basert på kravkode
        unique_requirements = {req.code: req for req in all_requirements}
        
        return list(unique_requirements.values())
    
    def calculate_compliance_score(self) -> float:
        """Beregner samlet etterlevelsesscore basert på alle vurderinger."""
        scores = []
        
        if self.oslomodell_result:
            scores.append(self.oslomodell_result.confidence)
        
        if self.miljokrav_result:
            scores.append(self.miljokrav_result.confidence)
        
        if self.triage_result:
            # Map triage color to score
            color_scores = {
                TriageColor.GREEN: 1.0,
                TriageColor.YELLOW: 0.6,
                TriageColor.RED: 0.3
            }
            scores.append(color_scores.get(self.triage_result.color, 0.5))
        
        return sum(scores) / len(scores) if scores else 0.0