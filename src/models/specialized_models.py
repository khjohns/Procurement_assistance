# src/models/specialized_models.py
"""
Specialized models for different assessment agents.
Extends base models with agent-specific fields.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from .base_models import (
    BaseMetadata, BaseProcurementInput, BaseAssessment, 
    Requirement, RequirementException
)
from .enums import (
    RiskLevel, RiskType, DueDiligenceRequirement, ReservedContractArea,
    EnvironmentalRequirementType, TransportType, TriageColor, ConditionOperator
)

# ==============================================================================
# OSLOMODELL MODELS
# ==============================================================================

# --- Nestede klasser for den nye regelstrukturen ---

class RuleCondition(BaseModel):
    """Representerer én enkelt betingelse som må være oppfylt."""
    description: str = Field(description="En lesbar beskrivelse av betingelsen.")
    field: str = Field(description="Datafeltet betingelsen gjelder for (f.eks. 'kontraktsverdi').")
    operator: str = Field(description="Operatoren som brukes for sammenligning (f.eks. '>', 'in', 'between').")
    value: Any = Field(description="Verdien betingelsen skal sammenlignes mot.")

class RuleSet(BaseModel):
    """Grupperer et sett med betingelser som til sammen utgjør ett logisk scenario."""
    scenario: str = Field(description="En kort beskrivelse av når denne regelgruppen gjelder.")
    applies_to_codes: List[str] = Field(default_factory=list, description="Kravkoder som utløses av dette scenarioet.")
    conditions: List[RuleCondition] = Field(default_factory=list, description="Listen over betingelser for dette scenarioet.")

class OslomodellMetadata(BaseMetadata):
    """
    Spesialisert metadata for Oslomodell-chunks, nå oppdatert
    med en nestet regelstruktur.
    """
    
    value_thresholds: Dict[str, int] = Field(default_factory=dict, description="Generelle verditerskler nevnt i teksten.")
    
    # Aktsomhetsvurderinger
    due_diligence_set: Optional[DueDiligenceRequirement] = Field(None, description="Pålagt sett med krav til aktsomhetsvurdering.")
    
    # Underleverandører
    max_subcontractor_levels: Optional[int] = Field(None, description="Maksimalt tillatt antall ledd med underleverandører.")
    subcontractor_conditions: List[Dict[str, Any]] = Field(default_factory=list, description="Spesielle betingelser knyttet til underleverandører.")
    
    # Lærlinger
    apprentice_required: Optional[bool] = Field(None, description="Hvorvidt det er krav om lærling.")
    apprentice_threshold: Optional[int] = Field(None, description="Verditerskel for lærlingekrav.")

class OslomodellInput(BaseProcurementInput):
    """Input for Oslomodell assessment."""
    
    # Risk factors
    known_risks: List[RiskType] = Field(default_factory=list, description="Known risk types")
    previous_incidents: Optional[bool] = Field(None, description="Previous compliance incidents")
    
    # Market info
    supplier_count: Optional[int] = Field(None, description="Number of potential suppliers")
    international_suppliers: Optional[bool] = Field(None, description="International suppliers involved")
    
    # Construction specific
    construction_site: Optional[bool] = Field(None, description="Has construction site")
    
    # Service specific
    service_area: Optional[str] = Field(None, description="Service area (e.g., 'renhold', 'kantine')")
    reserved_contract_applicable: Optional[bool] = Field(None, description="Reserved contract applicable")

class ApprenticeshipRequirement(BaseModel):
    """Structured model for apprenticeship requirements."""
    
    required: bool = Field(..., description="Whether apprentices required")
    reason: str = Field(..., description="Reason for requirement")
    minimum_count: int = Field(default=0, description="Minimum apprentices", ge=0)
    applicable_trades: List[str] = Field(default_factory=list, description="Relevant trades")
    threshold_exceeded: bool = Field(default=False, description="Threshold exceeded")

class OslomodellAssessment(BaseAssessment):
    """Oslomodell assessment output."""
    
    agent_name: str = Field(default="oslomodell_agent")
    
    # Risk assessments for seriøsitetskrav
    labor_risk_assessment: RiskLevel = Field(..., description="Labor crime risk")
    social_dumping_risk: RiskLevel = Field(..., description="Social dumping risk")
    
    # Risk assessments for aktsomhetsvurderinger
    rights_risk_assessment: RiskLevel = Field(..., description="Human rights risk")
    corruption_risk: RiskLevel = Field(..., description="Corruption risk")
    occupation_risk: RiskLevel = Field(..., description="Occupation risk")
    international_law_risk: RiskLevel = Field(..., description="International law risk")
    environment_risk: RiskLevel = Field(..., description="Environmental risk")
    
    # Requirements
    required_requirements: List[Requirement] = Field(default_factory=list, description="Applicable requirements")
    
    # Structured sub-assessments
    subcontractor_levels: int = Field(..., ge=0, le=2, description="Max subcontractor levels")
    subcontractor_justification: str = Field(..., description="Justification for levels")
    
    apprenticeship_requirement: Optional[ApprenticeshipRequirement] = Field(None, description="Apprenticeship details")
    
    due_diligence_requirement: Optional[DueDiligenceRequirement] = Field(None, description="Due diligence set")
    
    # Specific Oslomodell metadata
    applicable_instruction_points: List[str] = Field(default_factory=list, description="Relevant instruction points")
    identified_risk_areas: List[str] = Field(default_factory=list, description="Identified risk areas")

# ==============================================================================
# ENVIRONMENTAL MODELS
# ==============================================================================

class EnvironmentalMetadata(BaseMetadata):
    """Specialized metadata for Environmental chunks."""
    
    # Environmental-specific fields
    environmental_category: Optional[str] = Field(None, description="Environmental category")
    emission_requirements: List[str] = Field(default_factory=list, description="Emission requirements")
    
    # Transport
    transport_types: List[TransportType] = Field(default_factory=list, description="Transport types")
    zero_emission_required: Optional[bool] = Field(None, description="Zero emission requirement")
    biofuel_alternative: Optional[bool] = Field(None, description="Biofuel alternative allowed")
    
    # Incentives and deadlines
    incentive_programs: List[Dict[str, Any]] = Field(default_factory=list, description="Incentive programs")
    phase_out_date: Optional[datetime] = Field(None, description="Phase-out date")
    implementation_deadline: Optional[datetime] = Field(None, description="Implementation deadline")
    
    # Circular economy
    circular_requirements: List[str] = Field(default_factory=list, description="Circular economy requirements")
    waste_management: Optional[Dict[str, Any]] = Field(None, description="Waste management requirements")

class EnvironmentalInput(BaseProcurementInput):
    """Input for Environmental assessment."""
    
    # Transport
    involves_transport: bool = Field(default=False, description="Involves transport")
    transport_type: Optional[TransportType] = Field(None, description="Type of transport")
    transport_volume: Optional[int] = Field(None, description="Transport volume")
    
    # Energy
    energy_consumption_kwh: Optional[int] = Field(None, description="Energy consumption", ge=0)
    renewable_energy_available: Optional[bool] = Field(None, description="Renewable energy available")
    
    # Materials
    involves_construction_materials: Optional[bool] = Field(None, description="Involves construction materials")
    recyclable_materials: Optional[bool] = Field(None, description="Uses recyclable materials")
    
    # Location
    urban_area: Optional[bool] = Field(None, description="In urban area")
    environmental_zone: Optional[bool] = Field(None, description="In environmental zone")

class TransportRequirement(BaseModel):
    """Structured model for transport requirements."""
    
    transport_type: TransportType = Field(..., description="Type of transport")
    zero_emission_required: bool = Field(..., description="Zero emission required")
    biofuel_alternative: bool = Field(..., description="Biofuel alternative allowed")
    deadline: Optional[datetime] = Field(None, description="Implementation deadline")
    incentive_amount: Optional[int] = Field(None, description="Incentive amount in NOK")

class EnvironmentalAssessment(BaseAssessment):
    """Environmental assessment output."""
    
    agent_name: str = Field(default="environmental_agent")
    
    # Overall environmental assessment
    environmental_risk: RiskLevel = Field(..., description="Overall environmental risk")
    climate_impact: RiskLevel = Field(..., description="Climate impact assessment")
    
    # Requirements
    applied_requirements: List[Requirement] = Field(default_factory=list, description="Environmental requirements")
    transport_requirements: List[TransportRequirement] = Field(default_factory=list, description="Transport requirements")
    
    # Exceptions and minimum requirements
    exceptions_recommended: List[RequirementException] = Field(default_factory=list, description="Recommended exceptions")
    minimum_biofuel_required: bool = Field(default=False, description="Minimum biofuel requirement")
    
    # Important deadlines
    important_deadlines: Dict[str, datetime] = Field(default_factory=dict, description="Important deadlines")
    
    # Documentation and follow-up
    documentation_requirements: List[str] = Field(default_factory=list, description="Documentation requirements")
    follow_up_points: List[str] = Field(default_factory=list, description="Contract follow-up points")
    
    market_dialogue_recommended: bool = Field(default=False, description="Market dialogue recommended")
    
    # Award criteria
    award_criteria_recommended: List[str] = Field(default_factory=list, description="Recommended award criteria")

# ==============================================================================
# TRIAGE MODELS
# ==============================================================================

class TriageInput(BaseProcurementInput):
    """Input for Triage assessment (uses base model)."""
    pass  # No additional fields needed

class TriageAssessment(BaseAssessment):
    """Triage assessment output."""
    
    agent_name: str = Field(default="triage_agent")
    
    color: TriageColor = Field(..., description="Triage classification")
    reasoning: str = Field(..., description="Classification reasoning")
    
    risk_factors: List[str] = Field(default_factory=list, description="Identified risk factors")
    mitigation_measures: List[str] = Field(default_factory=list, description="Risk mitigation measures")
    
    requires_special_attention: bool = Field(default=False, description="Requires special attention")
    escalation_recommended: bool = Field(default=False, description="Escalation recommended")

# ==============================================================================
# PROTOCOL MODELS
# ==============================================================================

class ProtocolInput(BaseModel):
    """Input for protocol generation."""
    
    procurement_id: str = Field(..., description="Procurement ID")
    assessment_ids: List[str] = Field(..., description="Assessment IDs to include")
    protocol_type: str = Field(default="standard", description="Type of protocol")
    include_sections: List[str] = Field(default_factory=list, description="Sections to include")

class ProtocolOutput(BaseAssessment):
    """Protocol generation output."""
    
    agent_name: str = Field(default="protocol_generator")
    
    content: str = Field(..., description="Protocol content")
    protocol_type: str = Field(..., description="Protocol type")
    
    sections: List[str] = Field(default_factory=list, description="Protocol sections")
    
    # References to assessments
    based_on_assessments: List[str] = Field(default_factory=list, description="Assessment IDs used")
    
    approval_status: str = Field(default="draft", description="Approval status: draft/review/approved")
    version: str = Field(default="1.0", description="Version number")