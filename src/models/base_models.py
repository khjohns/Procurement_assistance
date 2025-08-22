# src/models/base_models.py
"""
Base models for the AI Agent SDK.
These are the foundation models that other models inherit from.
"""
from typing import List, Dict, Optional, Any, Union, Literal, Annotated
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from abc import ABC, abstractmethod
import uuid

from .enums import (
    SystemStatus, DocumentType, ProcurementCategory, ProcurementSubCategory, 
    RequirementSource, RequirementCategory, RiskLevel, ChunkType,
    RiskType, RuleStatus, ConditionOperator, RuleField, RequirementType,
    ProcurementPhase, RequirementModality
)

# ==============================================================================
# RULE SYSTEM COMPONENTS
# ==============================================================================
# Define rule components first, as they're used by other models

class BaseCondition(BaseModel):
    """Base model for rule conditions."""
    operator: ConditionOperator
    
    class Config:
        use_enum_values = False


class CategoryCondition(BaseCondition):
    """Condition for procurement category matching."""
    field: Literal["anskaffelsestype"]  # RuleField.PROCUREMENT_CATEGORY value
    value: Union[ProcurementCategory, List[ProcurementCategory]]
    
    @field_validator('value')
    def validate_category_value(cls, v):
        """Ensure value is valid procurement category."""
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, ProcurementCategory):
                    raise ValueError(f"All values must be ProcurementCategory enums, got {type(item)}")
        elif not isinstance(v, ProcurementCategory):
            raise ValueError(f"Value must be ProcurementCategory enum, got {type(v)}")
        return v

class SubCategoryCondition(BaseCondition):
    """Condition for procurement subcategory matching."""
    field: Literal["subcategory"]
    value: Union[ProcurementSubCategory, List[ProcurementSubCategory]]
    
    @field_validator('value')
    def validate_subcategory_value(cls, v):
        """Ensure value is valid procurement subcategory."""
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, ProcurementSubCategory):
                    raise ValueError(f"All values must be ProcurementSubCategory enums, got {type(item)}")
        elif not isinstance(v, ProcurementSubCategory):
            raise ValueError(f"Value must be ProcurementSubCategory enum, got {type(v)}")
        return v

class ValueCondition(BaseCondition):
    """Condition for procurement value thresholds."""
    field: Literal["kontraktsverdi"]  # RuleField.PROCUREMENT_VALUE value
    value: Union[int, List[int]]
    
    @field_validator('value')
    def validate_numeric_value(cls, v):
        """Ensure value is valid number or list of numbers."""
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, (int, float)):
                    raise ValueError(f"All values must be numeric, got {type(item)}")
                if item < 0:
                    raise ValueError(f"Values cannot be negative: {item}")
        elif not isinstance(v, (int, float)):
            raise ValueError(f"Value must be numeric, got {type(v)}")
        elif v < 0:
            raise ValueError(f"Value cannot be negative: {v}")
        return v


class RiskLevelCondition(BaseCondition):
    """Condition for general risk level assessment."""
    field: Literal["risiko_nivaa"]  # <-- Endret navn for å være utvetydig
    value: Union[RiskLevel, List[RiskLevel]]
    
    @field_validator('value')
    def validate_risk_level(cls, v):
        """Ensure value is valid risk level."""
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, RiskLevel):
                    raise ValueError(f"All values must be RiskLevel enums, got {type(item)}")
        elif not isinstance(v, RiskLevel):
            raise ValueError(f"Value must be RiskLevel enum, got {type(v)}")
        return v


class RiskTypeCondition(BaseCondition):
    """Condition for specific risk type assessment."""
    field: Literal["risiko_type"]   # <-- Endret navn for å være utvetydig
    value: Union[RiskType, List[RiskType]]
    
    @field_validator('value')
    def validate_risk_type(cls, v):
        """Ensure value is valid risk type."""
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, RiskType):
                    raise ValueError(f"All values must be RiskType enums, got {type(item)}")
        elif not isinstance(v, RiskType):
            raise ValueError(f"Value must be RiskType enum, got {type(v)}")
        return v


class DurationCondition(BaseCondition):
    """Condition for contract duration."""
    field: Union[Literal["kontraktsvarighet_år"], Literal["varighet_måneder"]]
    value: Union[int, List[int]]
    
    @field_validator('value')
    def validate_duration(cls, v):
        """Ensure duration is valid."""
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, int) or item < 0:
                    raise ValueError(f"Duration must be non-negative integer, got {item}")
        elif not isinstance(v, int) or v < 0:
            raise ValueError(f"Duration must be non-negative integer, got {v}")
        return v

class ReferenceCondition(BaseCondition):
    """Condition based on reference to another section."""
    field: Literal["referanse"] 
    value: str # f.eks. "punkt 4, 5, 6 og 7"

    @field_validator('value')
    def validate_reference_value(cls, v):
        """Ensure reference value is a non-empty string."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Reference value must be a non-empty string")
        return v.strip()

class PhaseCondition(BaseCondition):
    """Condition based on the procurement phase."""
    field: Literal["fase"]
    value: ProcurementPhase

    @field_validator('value')
    def validate_phase_value(cls, v):
        """Ensure value is a valid ProcurementPhase enum."""
        # Pydantic validerer enum-typen automatisk, 
        # men en eksplisitt sjekk kan være nyttig for klarhet og fremtidige utvidelser.
        if not isinstance(v, ProcurementPhase):
            # Denne feilen vil normalt bli fanget av Pydantic før validatoren kjører,
            # men det er god praksis å ha den her for robusthet.
            raise ValueError(f"Value must be a ProcurementPhase enum, got {type(v)}")
        return v

class ContractScopeCondition(BaseCondition):
    """Condition for whether the procurement is covered by a standard contract."""
    field: Literal["standardkontrakt_dekning"]
    # VI FJERNER 'value' OG BRUKER 'operator' FOR Å DEFINERE TILSTANDEN
    operator: Literal[ConditionOperator.IS_TRUE, ConditionOperator.IS_FALSE] = Field(
        ..., 
        description="IS_TRUE if covered, IS_FALSE if not covered."
    )

class QualitativeCondition(BaseCondition):
    """Condition for complex, descriptive circumstances."""
    field: Literal["kvalitativ_betingelse"]
    value: Union[str, List[str]]

class RuleApplicabilityCondition(BaseCondition):
    """Condition that depends on another rule being applicable."""
    field: Literal["regel_avhengighet"]
    value: str  # The rule_id of the rule it depends on

class RequirementCondition(BaseCondition):
    """Condition that depends on another requirement being applicable."""
    field: Literal["krav_aktivert"]
    value: Union[str, List[str]] # The requirement code(s) to check for
    operator: Literal[
        ConditionOperator.IN, 
        ConditionOperator.NOT_IN
    ] = Field(
        default=ConditionOperator.IN,
        description="IN checks if any of the listed requirements are active. NOT_IN checks if none are."
    )

    @field_validator('value')
    def validate_requirement_code(cls, v):
        """Ensure value is a non-empty string or list of non-empty strings."""
        if isinstance(v, str):
            if not v.strip():
                raise ValueError("Requirement code value cannot be an empty string")
            return v.strip()
        if isinstance(v, list):
            if not v:
                raise ValueError("Requirement code list cannot be empty")
            validated_list = []
            for item in v:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError("All requirement codes in the list must be non-empty strings")
                validated_list.append(item.strip())
            return validated_list
        raise TypeError("Value must be a string or a list of strings")


# Discriminated Union for all condition types
Condition = Annotated[
    Union[
        CategoryCondition,
        SubCategoryCondition,
        ValueCondition,
        RiskLevelCondition,
        RiskTypeCondition,
        DurationCondition,
        ReferenceCondition,
        PhaseCondition,
        ContractScopeCondition,
        QualitativeCondition,
        RuleApplicabilityCondition,
        RequirementCondition 
    ],
    Field(discriminator='field')
]


# ==============================================================================
# REQUIREMENT DEFINITION
# ==============================================================================

class Requirement(BaseModel):
    """
    Central model defining a procurement requirement.
    This is the single source of truth for what a requirement is.
    """
    # Identification
    code: str = Field(..., description="Unique requirement code, e.g. 'A', 'MK-01'")
    name: str = Field(..., description="Short, human-readable requirement name")
    
    # Classification
    description: Optional[str] = Field(None, description="Detailed description and purpose")
    source: RequirementSource = Field(..., description="Source of requirement (e.g. Oslomodellen)")
    category: RequirementCategory = Field(..., description="Main category (e.g. integrity)")
    type: RequirementType = Field(..., description="Type of requirement (e.g. contract)")
    mitigates_risks: List[RiskType] = Field(
        default_factory=list, 
        description="Risk types this requirement addresses"
    )
    status: RuleStatus = Field(
        default=RuleStatus.ACTIVE, 
        description="Lifecycle status"
    )

    parameters: Optional[Dict[str, Any]] = Field(None, description="Structured parameters, e.g. {'max_subcontractor_levels': 1}")
    
    # Application rules
    modality: RequirementModality = Field(..., description="The legal force of the requirement (e.g., mandatory, optional)")
    exceptions_allowed: bool = Field(default=False, description="Can exceptions be made?")
    
    # Metadata
    reference: Optional[str] = Field(None, description="Legal or regulatory reference")
    deadline: Optional[datetime] = Field(None, description="Implementation deadline")
    verification_method: Optional[str] = Field(None, description="How to verify compliance")
    documentation_required: List[str] = Field(
        default_factory=list,
        description="Required documentation types"
    )
    
    # Related requirements
    depends_on: List[str] = Field(
        default_factory=list,
        description="Other requirement codes this depends on"
    )
    conflicts_with: List[str] = Field(
        default_factory=list,
        description="Requirement codes that conflict with this"
    )
    
    class Config:
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==============================================================================
# RULE DEFINITION
# ==============================================================================

class Rule(BaseModel):
    """
    Defines the logical conditions that activate a specific requirement.
    Answers: "When does requirement X apply?"
    """
    rule_id: str = Field(..., description="Unique identifier for this rule")
    description: str = Field(..., description="Human-readable rule description")

    justification_reference: Optional[str] = Field(
        None,
        description="Direct reference to the source text justifying the rule (e.g., 'jf. punkt 7.1')")
    
    # Conditions that must be met
    conditions: List[Condition] = Field(
        ...,
        description="List of conditions that trigger this rule"
    )
    
    # Logical operator for combining conditions
    condition_logic: Literal["AND", "OR"] = Field(
        default="AND",
        description="How to combine multiple conditions"
    )
    
    # What this rule activates
    activates_requirement_codes: List[str] = Field(
        ...,
        description="Requirement codes activated when conditions are met"
    )
    
    # Rule metadata
    priority: int = Field(
        default=0,
        description="Priority when multiple rules apply (higher = higher priority)"
    )
    overrides_rules: List[str] = Field(
        default_factory=list,
        description="Rule IDs this rule overrides"
    )
    valid_from: Optional[datetime] = Field(None, description="When rule becomes active")
    valid_until: Optional[datetime] = Field(None, description="When rule expires")
    
    @model_validator(mode='after')
    def validate_temporal_validity(self):
        """Ensure valid_from is before valid_until if both are set."""
        if self.valid_from and self.valid_until:
            if self.valid_from >= self.valid_until:
                raise ValueError("valid_from must be before valid_until")
        return self
    
    def is_active(self, at_date: Optional[datetime] = None) -> bool:
        """Check if rule is active at given date."""
        check_date = at_date or datetime.now()
        
        if self.valid_from and check_date < self.valid_from:
            return False
        if self.valid_until and check_date > self.valid_until:
            return False
        return True
    
    class Config:
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==============================================================================
# EXCEPTION MODEL
# ==============================================================================

class RequirementException(BaseModel):
    """Model for requirement exceptions."""
    
    requirement_code: str = Field(..., description="Requirement code for exception")
    reason: str = Field(..., description="Reason for exception")
    risk_assessment: str = Field(..., description="Assessment of risks from exception")
    
    alternative_measures: List[str] = Field(
        default_factory=list, 
        description="Alternative measures to mitigate risk"
    )
    
    # Approval
    approved_by: Optional[str] = Field(None, description="Who approved exception")
    approval_date: Optional[datetime] = Field(None, description="When approved")
    approval_level: Optional[str] = Field(None, description="Required approval level")
    
    # Validity
    valid_from: datetime = Field(default_factory=datetime.now)
    valid_until: Optional[datetime] = Field(None, description="Exception expiry")
    
    # Documentation
    documentation_provided: List[str] = Field(
        default_factory=list,
        description="Documentation supporting exception"
    )
    conditions_attached: List[str] = Field(
        default_factory=list,
        description="Conditions for exception approval"
    )
    
    @model_validator(mode='after')
    def validate_temporal_validity(self):
        """Ensure valid_from is before valid_until if both are set."""
        if self.valid_until and self.valid_from >= self.valid_until:
            raise ValueError("valid_from must be before valid_until")
        return self
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==============================================================================
# BASE METADATA MODEL
# ==============================================================================

class BaseMetadata(BaseModel):
    """Base metadata model for all knowledge chunks."""
    
    # Identity
    chunk_id: str = Field(..., description="Unique chunk identifier")
    source_document: str = Field(..., description="Source document name")
    document_type: DocumentType = Field(..., description="Type of source document")
    
    # Content
    title: str = Field(..., description="Chunk title")
    content: str = Field(..., description="Full text content")
    summary: str = Field(..., description="Brief summary for search")
    objectives: List[str] = Field(default_factory=list, description="The strategic goals or 'WHY' behind the chunk's content")
    
    # Hierarchy
    source_page: Optional[int] = Field(None, description="Page number in source")
    section_number: Optional[str] = Field(None, description="Section identifier")
    parent_chunk_id: Optional[str] = Field(None, description="Parent chunk reference")
    child_chunk_ids: List[str] = Field(default_factory=list, description="Child chunk references")
    related_chunk_ids: List[str] = Field(default_factory=list, description="Related chunks")
    references_to_other_docs: List[str] = Field(
        default_factory=list, 
        description="External document references"
    )
    
    # Status and versioning
    status: SystemStatus = Field(default=SystemStatus.ACTIVE)
    version: str = Field(default="1.0")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Search optimization
    keywords: List[str] = Field(default_factory=list, description="Keywords for search")
    semantic_tags: List[str] = Field(default_factory=list, description="Semantic tags")
    confidence_score: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0, 
        description="Metadata quality score"
    )
    
    # Chunk classification
    chunk_type: ChunkType = Field(
        default=ChunkType.RULE, 
        description="Type of chunk for filtering"
    )
    
    # Rules and requirements in this chunk
    rules: List[Rule] = Field(
        default_factory=list,
        description="Rules defined in this chunk"
    )
    requirements: List[Requirement] = Field(
        default_factory=list,
        description="Requirements defined in this chunk"
    )
    
    # Risk context
    addresses_risks: List[RiskType] = Field(
        default_factory=list,
        description="Risk types addressed in this chunk"
    )
    
    class Config:
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==============================================================================
# BASE INPUT MODEL
# ==============================================================================

class BaseProcurementInput(BaseModel):
    """Base input model for all procurement assessments."""
    
    # Core identification
    procurement_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique procurement identifier"
    )
    name: str = Field(..., description="Procurement name")
    description: Optional[str] = Field(None, description="Detailed description")
    
    # Core attributes
    value: int = Field(..., description="Estimated value in NOK excl. VAT", ge=0)
    category: ProcurementCategory = Field(..., description="Procurement category")
    subcategory: Optional[ProcurementSubCategory] = Field(None, description="Specialized subcategory")
    duration_months: int = Field(default=0, description="Contract duration in months", ge=0)

    case_number: Optional[str] = Field(None, description="Official case number (saksnr.)")
    project_number: Optional[str] = Field(None, description="Project number (prosjektnr.)")
    tender_deadline: Optional[datetime] = Field(None, description="The deadline for submitting tenders (tilbudsfrist)")
    
    # Risk assessment
    identified_risks: List[RiskType] = Field(
        default_factory=list,
        description="Identified risk types"
    )
    risk_level: Optional[RiskLevel] = Field(None, description="Overall risk assessment")
    
    # Supplier and market information
    potential_supplier: Optional[str] = Field(None, description="Potential preferred supplier")
    known_suppliers_count: int = Field(default=0, description="Number of known suppliers", ge=0)
    market_dialogue_completed: bool = Field(default=False, description="Market dialogue completed")
    
    # Construction and civil engineering
    includes_construction: bool = Field(default=False, description="Includes construction work")
    construction_site_size: Optional[int] = Field(None, description="Site size in m2", ge=0)
    involves_demolition: bool = Field(default=False, description="Includes demolition")
    involves_earthworks: bool = Field(default=False, description="Includes earthworks")
    involves_mass_transport: bool = Field(default=False, description="Includes mass transport")
    
    # Administrative details
    estimated_suppliers: int = Field(default=0, description="Estimated number of bidders", ge=0)
    innovation_potential: bool = Field(default=False, description="Innovation potential")
    
    # Compliance
    risk_assessment_completed: bool = Field(default=False, description="Risk assessment done")
    previous_contracts: Optional[List[str]] = Field(None, description="Related previous contracts")
    
    # Metadata
    requested_at: datetime = Field(default_factory=datetime.now)
    requested_by: Optional[str] = Field(None, description="User requesting assessment")
    organization: Optional[str] = Field(None, description="Organization name")
    
    @field_validator('value')
    def validate_value(cls, v):
        """Validate procurement value."""
        if v < 0:
            raise ValueError("Procurement value cannot be negative")
        if v > 10_000_000_000:  # 10 billion NOK
            raise ValueError("Value seems unrealistically high (>10B NOK)")
        return v
    
    @field_validator('duration_months')
    def validate_duration(cls, v):
        """Validate contract duration."""
        if v < 0:
            raise ValueError("Duration cannot be negative")
        if v > 120:  # 10 years
            raise ValueError("Duration over 10 years requires special handling")
        return v
    
    class Config:
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==============================================================================
# BASE ASSESSMENT MODEL
# ==============================================================================

class BaseAssessment(BaseModel):
    """Base assessment output for all agents."""
    
    # Link to input
    procurement_id: str = Field(..., description="Reference to procurement")
    procurement_name: str = Field(..., description="Procurement name")
    
    # Assessment metadata
    assessment_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique assessment identifier"
    )
    agent_name: str = Field(..., description="Agent that performed assessment")
    assessment_date: datetime = Field(default_factory=datetime.now)
    
    # Results
    applicable_requirements: List[Requirement] = Field(
        default_factory=list,
        description="Requirements that apply"
    )
    triggered_rules: List[Rule] = Field(
        default_factory=list,
        description="Rules that were triggered"
    )
    exceptions_made: List[RequirementException] = Field(
        default_factory=list,
        description="Exceptions for this assessment"
    )
    
    # Confidence and quality
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Assessment confidence")
    information_gaps: List[str] = Field(default_factory=list, description="Missing information")
    assumptions_made: List[str] = Field(default_factory=list, description="Assumptions made")
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    warnings: List[str] = Field(default_factory=list, description="Warnings")
    follow_up_required: List[str] = Field(default_factory=list, description="Follow-up actions")
    
    # Status
    status: SystemStatus = Field(default=SystemStatus.PROCESSED)
    requires_review: bool = Field(default=False, description="Needs human review")
    review_notes: Optional[str] = Field(None, description="Notes for reviewer")
    
    # References and sources
    context_documents_used: List[str] = Field(
        default_factory=list, 
        description="Documents used"
    )
    chunks_used: List[str] = Field(
        default_factory=list, 
        description="Chunk IDs used"
    )
    reasoning_steps: List[str] = Field(
        default_factory=list, 
        description="Reasoning steps"
    )
    confidence_factors: Dict[str, float] = Field(
        default_factory=dict, 
        description="Confidence breakdown"
    )
    
    # Performance metrics
    processing_time_ms: Optional[int] = Field(None, description="Processing time")
    tokens_used: Optional[int] = Field(None, description="LLM tokens used")
    model_version: str = Field(default="1.0", description="Model version used")
    
    class Config:
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==============================================================================
# INTERFACES
# ==============================================================================

class IKnowledgeRepository(ABC):
    """Interface for knowledge repository."""
    
    @abstractmethod
    async def search_chunks(
        self,
        query: str,
        metadata_filters: Dict[str, Any],
        limit: int = 10
    ) -> List[BaseMetadata]:
        """Search for relevant chunks."""
        pass
    
    @abstractmethod
    async def get_chunk_by_id(self, chunk_id: str) -> Optional[BaseMetadata]:
        """Get specific chunk by ID."""
        pass
    
    @abstractmethod
    async def get_requirements_by_codes(
        self, 
        codes: List[str]
    ) -> List[Requirement]:
        """Get requirements by their codes."""
        pass
    
    @abstractmethod
    async def get_active_rules(
        self,
        at_date: Optional[datetime] = None
    ) -> List[Rule]:
        """Get all active rules at given date."""
        pass


class IAssessmentAgent(ABC):
    """Interface for assessment agents."""
    
    @abstractmethod
    async def assess(
        self,
        procurement: BaseProcurementInput,
        chunks: List[BaseMetadata]
    ) -> BaseAssessment:
        """Perform assessment."""
        pass
    
    @abstractmethod
    def get_required_metadata_type(self) -> type:
        """Return required metadata type."""
        pass
    
    @abstractmethod
    async def evaluate_rules(
        self,
        procurement: BaseProcurementInput,
        rules: List[Rule]
    ) -> List[Rule]:
        """Evaluate which rules apply to procurement."""
        pass