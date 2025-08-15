# src/models/base_models.py
"""
Base models for the AI Agent SDK.
These are the foundation models that other models inherit from.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from abc import ABC, abstractmethod

from .enums import (
    SystemStatus, DocumentType, ProcurementCategory, 
    RequirementSource, RequirementCategory, RiskLevel, ChunkType
)

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
    
    # Hierarchy
    source_page: Optional[int] = Field(None, description="Page number in source")
    section_number: Optional[str] = Field(None, description="Section identifier")
    parent_chunk_id: Optional[str] = Field(None, description="Parent chunk reference")
    child_chunk_ids: List[str] = Field(default_factory=list, description="Child chunk references")
    references_to_other_docs: List[str] = Field(default_factory=list, description="External document references")
    
    # Status and versioning
    status: SystemStatus = Field(default=SystemStatus.ACTIVE)
    version: str = Field(default="1.0")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Search optimization
    keywords: List[str] = Field(default_factory=list, description="Keywords for search")
    semantic_tags: List[str] = Field(default_factory=list, description="Semantic tags")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Metadata quality score")

    chunk_type: Optional[ChunkType] = Field(
        default=ChunkType.RULE, 
        description="Type of chunk for filtering strategy"
    )
    
    rule_sets: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured rule conditions"
    )
    requirement_codes: List[str] = Field(
        default_factory=list,
        description="Applicable requirement codes"
    )
    
    risk_levels: List[RiskLevel] = Field(default_factory=list, description="Gjeldende risikonivåer.")
    
    class Config:
        use_enum_values = False  # Keep enum objects, not values
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ==============================================================================
# BASE INPUT MODEL
# ==============================================================================

class BaseProcurementInput(BaseModel):
    """Base input model for all procurement assessments."""
    
    # Core identification
    procurement_id: str = Field(..., description="Unique procurement identifier")
    name: str = Field(..., description="Procurement name")
    description: Optional[str] = Field(None, description="Detailed description")
    
    # Core attributes
    value: int = Field(..., description="Estimated value in NOK excl. VAT", ge=0)
    category: ProcurementCategory = Field(..., description="Procurement category")
    duration_months: int = Field(default=0, description="Contract duration in months", ge=0)
    
    # Supplier and market information
    potential_supplier: Optional[str] = Field(None, description="Potential preferred supplier")
    known_suppliers_count: int = Field(default=0, description="Number of known suppliers", ge=0)
    market_dialogue_completed: bool = Field(default=False, description="Market dialogue completed")
    
    # Construction and civil engineering
    includes_construction: bool = Field(default=False, description="Includes construction work")
    construction_site_size: Optional[int] = Field(None, description="Site size in m2", ge=0)
    involves_demolition: bool = Field(default=False, description="Includes demolition")
    involves_earthworks: bool = Field(default=False, description="Includes earthworks")
    
    # Administrative details
    estimated_suppliers: int = Field(default=0, description="Estimated number of bidders", ge=0)
    innovation_potential: bool = Field(default=False, description="Innovation potential")
    
    # Risk and compliance
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
    assessment_id: str = Field(..., description="Unique assessment identifier")
    agent_name: str = Field(..., description="Agent that performed assessment")
    assessment_date: datetime = Field(default_factory=datetime.now)
    
    # Results
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Assessment confidence")
    information_gaps: List[str] = Field(default_factory=list, description="Missing information")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    warnings: List[str] = Field(default_factory=list, description="Warnings")
    status: SystemStatus = Field(default=SystemStatus.PROCESSED)
    
    # References and sources
    context_documents_used: List[str] = Field(default_factory=list, description="Documents used")
    chunks_used: List[str] = Field(default_factory=list, description="Chunk IDs used")
    reasoning: List[str] = Field(default_factory=list, description="Reasoning steps")
    confidence_factors: Dict[str, float] = Field(default_factory=dict, description="Confidence breakdown")
    
    # Performance metrics
    processing_time_ms: Optional[int] = Field(None, description="Processing time")
    model_version: str = Field(default="1.0", description="Model version used")
    
    class Config:
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ==============================================================================
# BASE REQUIREMENT MODEL
# ==============================================================================

class Requirement(BaseModel):
    """Generic model for any requirement from regulations."""
    
    code: str = Field(..., description="Unique requirement code (e.g., 'A', 'MK-01')")
    name: str = Field(..., description="Short requirement name")
    description: Optional[str] = Field(None, description="Detailed description")
    mandatory: bool = Field(..., description="Whether requirement is mandatory")
    source: RequirementSource = Field(..., description="Source regulation")
    category: RequirementCategory = Field(..., description="Requirement category")
    
    # Optional metadata
    reference: Optional[str] = Field(None, description="Legal reference")
    deadline: Optional[datetime] = Field(None, description="Implementation deadline")
    exceptions_allowed: bool = Field(default=False, description="Whether exceptions allowed")
    verification_method: Optional[str] = Field(None, description="How to verify compliance")
    
    class Config:
        use_enum_values = False
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ==============================================================================
# BASE EXCEPTION MODEL
# ==============================================================================

class RequirementException(BaseModel):
    """Model for requirement exceptions."""
    
    requirement_code: str = Field(..., description="Requirement code for exception")
    reason: str = Field(..., description="Reason for exception")
    alternative_measures: List[str] = Field(default_factory=list, description="Alternative measures")
    documentation_required: bool = Field(default=True, description="Documentation needed")
    approved_by: Optional[str] = Field(None, description="Who approved exception")
    approval_date: Optional[datetime] = Field(None, description="Approval date")
    
    class Config:
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