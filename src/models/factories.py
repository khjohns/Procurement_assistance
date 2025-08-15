# src/models/factories.py
"""
Factory patterns and utility functions for model creation.
Provides centralized object creation with validation.
"""
from typing import Dict, Any, Type, Optional, Union
from datetime import datetime
import uuid

from .base_models import BaseMetadata, BaseAssessment, BaseProcurementInput
from .specialized_models import (
    OslomodellMetadata, OslomodellInput, OslomodellAssessment,
    EnvironmentalMetadata, EnvironmentalInput, EnvironmentalAssessment,
    TriageInput, TriageAssessment
)
from .aggregation_models import ComprehensiveAssessment, AssessmentRequest

# ==============================================================================
# METADATA FACTORY
# ==============================================================================

class MetadataFactory:
    """Factory for creating appropriate metadata objects."""
    
    _metadata_types = {
        "base": BaseMetadata,
        "oslomodell": OslomodellMetadata,
        "environmental": EnvironmentalMetadata
    }
    
    @classmethod
    def create_metadata(
        cls,
        agent_type: str,
        data: Dict[str, Any]
    ) -> BaseMetadata:
        """
        Create metadata object based on agent type.
        
        Args:
            agent_type: Type of agent ("oslomodell", "environmental", etc.)
            data: Dictionary with metadata fields
            
        Returns:
            Appropriate metadata object
            
        Raises:
            ValueError: If agent_type is unknown
        """
        metadata_class = cls._metadata_types.get(agent_type, BaseMetadata)
        
        # Add default values if missing
        if "chunk_id" not in data:
            data["chunk_id"] = str(uuid.uuid4())
        
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        
        if "updated_at" not in data:
            data["updated_at"] = datetime.now()
        
        return metadata_class(**data)
    
    @classmethod
    def register_metadata_type(cls, name: str, metadata_class: Type[BaseMetadata]) -> None:
        """Register a new metadata type."""
        cls._metadata_types[name] = metadata_class

# ==============================================================================
# INPUT FACTORY
# ==============================================================================

class InputFactory:
    """Factory for creating procurement input objects."""
    
    _input_types = {
        "base": BaseProcurementInput,
        "oslomodell": OslomodellInput,
        "environmental": EnvironmentalInput,
        "triage": TriageInput
    }
    
    @classmethod
    def create_input(
        cls,
        agent_type: str,
        data: Dict[str, Any]
    ) -> BaseProcurementInput:
        """
        Create input object based on agent type.
        
        Args:
            agent_type: Type of agent
            data: Dictionary with input fields
            
        Returns:
            Appropriate input object
        """
        input_class = cls._input_types.get(agent_type, BaseProcurementInput)
        
        # Add default procurement_id if missing
        if "procurement_id" not in data:
            data["procurement_id"] = str(uuid.uuid4())
        
        return input_class(**data)
    
    @classmethod
    def create_from_request(
        cls,
        request: Dict[str, Any],
        agent_type: str
    ) -> BaseProcurementInput:
        """
        Create input from a general request dictionary.
        Maps common fields to agent-specific fields.
        """
        # Extract common fields
        common_fields = {
            "procurement_id": request.get("id", str(uuid.uuid4())),
            "name": request.get("name", "Unnamed procurement"),
            "description": request.get("description"),
            "value": request.get("value", 0),
            "category": request.get("category", "tjeneste"),
            "duration_months": request.get("duration_months", 0)
        }
        
        # Add agent-specific fields
        if agent_type == "oslomodell":
            common_fields.update({
                "known_risks": request.get("risks", []),
                "construction_site": request.get("has_construction", False),
                "supplier_count": request.get("suppliers", 0)
            })
        elif agent_type == "environmental":
            common_fields.update({
                "involves_transport": request.get("transport", False),
                "transport_type": request.get("transport_type"),
                "urban_area": request.get("urban", False)
            })
        
        return cls.create_input(agent_type, common_fields)

# ==============================================================================
# ASSESSMENT FACTORY
# ==============================================================================

class AssessmentFactory:
    """Factory for creating assessment objects."""
    
    _assessment_types = {
        "base": BaseAssessment,
        "oslomodell": OslomodellAssessment,
        "environmental": EnvironmentalAssessment,
        "triage": TriageAssessment
    }
    
    @classmethod
    def create_assessment(
        cls,
        agent_type: str,
        data: Dict[str, Any]
    ) -> BaseAssessment:
        """
        Create assessment object based on agent type.
        
        Args:
            agent_type: Type of agent
            data: Dictionary with assessment data
            
        Returns:
            Appropriate assessment object
        """
        assessment_class = cls._assessment_types.get(agent_type, BaseAssessment)
        
        # Add default values
        if "assessment_id" not in data:
            data["assessment_id"] = str(uuid.uuid4())
        
        if "assessment_date" not in data:
            data["assessment_date"] = datetime.now()
        
        if "agent_name" not in data:
            data["agent_name"] = f"{agent_type}_agent"
        
        return assessment_class(**data)
    
    @classmethod
    def create_comprehensive(
        cls,
        procurement: BaseProcurementInput,
        assessments: Dict[str, BaseAssessment]
    ) -> ComprehensiveAssessment:
        """
        Create comprehensive assessment from individual assessments.
        
        Args:
            procurement: Original procurement request
            assessments: Dictionary of assessments by type
            
        Returns:
            Comprehensive assessment with aggregated results
        """
        comprehensive = ComprehensiveAssessment(
            request_id=str(uuid.uuid4()),
            procurement=procurement,
            triage_assessment=assessments.get("triage"),
            oslomodell_assessment=assessments.get("oslomodell"),
            environmental_assessment=assessments.get("environmental")
        )
        
        # Perform aggregations
        comprehensive.aggregate_requirements()
        comprehensive.calculate_overall_risk()
        comprehensive.calculate_overall_confidence()
        comprehensive.aggregate_recommendations()
        
        return comprehensive

# ==============================================================================
# VALIDATION UTILITIES
# ==============================================================================

class ModelValidator:
    """Utility class for model validation."""
    
    @staticmethod
    def validate_procurement_value(value: int) -> bool:
        """Validate procurement value is within reasonable range."""
        return 0 <= value <= 10_000_000_000
    
    @staticmethod
    def validate_duration(months: int) -> bool:
        """Validate contract duration."""
        return 0 <= months <= 120
    
    @staticmethod
    def validate_confidence_score(score: float) -> bool:
        """Validate confidence score is between 0 and 1."""
        return 0.0 <= score <= 1.0
    
    @staticmethod
    def validate_requirement_code(code: str) -> bool:
        """Validate requirement code format."""
        # Oslomodell codes: A-V
        if len(code) == 1 and 'A' <= code <= 'V':
            return True
        
        # Environmental codes: MK-XX
        if code.startswith("MK-") and len(code) == 5:
            return True
        
        # Other formats can be added here
        return False

# ==============================================================================
# CONVERSION UTILITIES
# ==============================================================================

class ModelConverter:
    """Utility class for converting between model formats."""
    
    @staticmethod
    def to_dict(model: BaseAssessment) -> Dict[str, Any]:
        """Convert Pydantic model to dictionary."""
        return model.model_dump(mode='json')
    
    @staticmethod
    def from_dict(data: Dict[str, Any], model_class: Type[BaseAssessment]) -> BaseAssessment:
        """Create model instance from dictionary."""
        return model_class(**data)
    
    @staticmethod
    def merge_assessments(
        assessments: list[BaseAssessment]
    ) -> Dict[str, Any]:
        """
        Merge multiple assessments into a single dictionary.
        Useful for database storage or API responses.
        """
        merged = {
            "assessments": [],
            "total_requirements": [],
            "all_recommendations": [],
            "all_warnings": []
        }
        
        for assessment in assessments:
            assessment_dict = assessment.model_dump(mode='json')
            merged["assessments"].append(assessment_dict)
            
            # Aggregate requirements
            if hasattr(assessment, "required_requirements"):
                merged["total_requirements"].extend(assessment.required_requirements)
            elif hasattr(assessment, "applied_requirements"):
                merged["total_requirements"].extend(assessment.applied_requirements)
            
            # Aggregate recommendations and warnings
            merged["all_recommendations"].extend(assessment.recommendations)
            merged["all_warnings"].extend(assessment.warnings)
        
        # Deduplicate
        merged["total_requirements"] = list({r.code: r for r in merged["total_requirements"]}.values())
        merged["all_recommendations"] = list(dict.fromkeys(merged["all_recommendations"]))
        merged["all_warnings"] = list(dict.fromkeys(merged["all_warnings"]))
        
        return merged

# ==============================================================================
# BUILDER PATTERNS
# ==============================================================================

class AssessmentRequestBuilder:
    """Builder pattern for creating assessment requests."""
    
    def __init__(self):
        self._procurement_data = {}
        self._assessments = ["triage"]  # Default to triage only
        self._priority = "normal"
        self._context = {}
        self._generate_protocol = True
    
    def with_procurement(self, **kwargs) -> 'AssessmentRequestBuilder':
        """Set procurement details."""
        self._procurement_data.update(kwargs)
        return self
    
    def with_assessments(self, *assessments: str) -> 'AssessmentRequestBuilder':
        """Specify which assessments to run."""
        self._assessments = list(assessments)
        return self
    
    def with_priority(self, priority: str) -> 'AssessmentRequestBuilder':
        """Set priority level."""
        if priority not in ["low", "normal", "high", "urgent"]:
            raise ValueError(f"Invalid priority: {priority}")
        self._priority = priority
        return self
    
    def with_context(self, **context) -> 'AssessmentRequestBuilder':
        """Add context information."""
        self._context.update(context)
        return self
    
    def without_protocol(self) -> 'AssessmentRequestBuilder':
        """Disable protocol generation."""
        self._generate_protocol = False
        return self
    
    def build(self) -> AssessmentRequest:
        """Build the assessment request."""
        # Create procurement input
        procurement = BaseProcurementInput(**self._procurement_data)
        
        return AssessmentRequest(
            procurement=procurement,
            requested_assessments=self._assessments,
            priority=self._priority,
            context=self._context,
            generate_protocol=self._generate_protocol
        )

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def create_default_procurement(name: str, value: int) -> BaseProcurementInput:
    """Create a procurement with default values for testing."""
    return BaseProcurementInput(
        procurement_id=str(uuid.uuid4()),
        name=name,
        value=value,
        category="tjeneste",
        duration_months=12,
        description=f"Test procurement: {name}"
    )

def create_mock_assessment(
    agent_type: str,
    procurement_id: str,
    confidence: float = 0.8
) -> BaseAssessment:
    """Create a mock assessment for testing."""
    base_data = {
        "procurement_id": procurement_id,
        "procurement_name": "Test procurement",
        "confidence_score": confidence,
        "recommendations": ["Test recommendation"],
        "warnings": []
    }
    
    # Add agent-specific required fields
    if agent_type == "oslomodell":
        base_data.update({
            "labor_risk_assessment": "lav",
            "social_dumping_risk": "lav",
            "rights_risk_assessment": "lav",
            "corruption_risk": "lav",
            "occupation_risk": "lav",
            "international_law_risk": "lav",
            "environment_risk": "lav",
            "subcontractor_levels": 2,
            "subcontractor_justification": "Standard vurdering"
        })
    elif agent_type == "environmental":
        base_data.update({
            "environmental_risk": "lav",
            "climate_impact": "lav"
        })
    elif agent_type == "triage":
        base_data.update({
            "color": "grønn",
            "reasoning": "Low value and risk"
        })
    
    return AssessmentFactory.create_assessment(agent_type, base_data)

def validate_assessment_completeness(assessment: BaseAssessment) -> tuple[bool, list[str]]:
    """
    Validate that an assessment has all required fields.
    
    Returns:
        Tuple of (is_valid, list_of_missing_fields)
    """
    missing_fields = []
    
    # Check base required fields
    required_base_fields = [
        "procurement_id", "procurement_name", "assessment_id",
        "agent_name", "confidence_score"
    ]
    
    for field in required_base_fields:
        if not getattr(assessment, field, None):
            missing_fields.append(field)
    
    # Check agent-specific fields
    if isinstance(assessment, OslomodellAssessment):
        oslomodell_fields = [
            "labor_risk_assessment", "social_dumping_risk",
            "subcontractor_levels", "subcontractor_justification"
        ]
        for field in oslomodell_fields:
            if getattr(assessment, field, None) is None:
                missing_fields.append(field)
    
    elif isinstance(assessment, EnvironmentalAssessment):
        env_fields = ["environmental_risk", "climate_impact"]
        for field in env_fields:
            if getattr(assessment, field, None) is None:
                missing_fields.append(field)
    
    elif isinstance(assessment, TriageAssessment):
        triage_fields = ["color", "reasoning"]
        for field in triage_fields:
            if not getattr(assessment, field, None):
                missing_fields.append(field)
    
    return len(missing_fields) == 0, missing_fields

# ==============================================================================
# EXPORT ALL PUBLIC INTERFACES
# ==============================================================================

__all__ = [
    # Factories
    'MetadataFactory',
    'InputFactory',
    'AssessmentFactory',
    
    # Utilities
    'ModelValidator',
    'ModelConverter',
    
    # Builder
    'AssessmentRequestBuilder',
    
    # Helper functions
    'create_default_procurement',
    'create_mock_assessment',
    'validate_assessment_completeness'
]