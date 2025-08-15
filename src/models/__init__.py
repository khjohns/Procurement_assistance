# src/models/__init__.py
"""
Unified model system for AI Agent SDK.
"""

# Import all enums
from .enums import *

# Import base models
from .base_models import (
    BaseMetadata,
    BaseProcurementInput,
    BaseAssessment,
    Requirement,
    RequirementException
)

# Import specialized models
from .specialized_models import (
    OslomodellMetadata,
    OslomodellInput,
    OslomodellAssessment,
    EnvironmentalMetadata,
    EnvironmentalInput,
    EnvironmentalAssessment,
    TriageInput,
    TriageAssessment
)

# Import aggregation models
from .aggregation_models import (
    AssessmentRequest,
    ComprehensiveAssessment,
    OrchestrationPlan,
    ExecutionLog
)

# Import factories
from .factories import (
    MetadataFactory,
    InputFactory,
    AssessmentFactory,
    AssessmentRequestBuilder
)

__all__ = [
    # Enums (list the main ones)
    'RiskLevel',
    'ProcurementCategory',
    'SystemStatus',
    
    # Base models
    'BaseMetadata',
    'BaseProcurementInput',
    'BaseAssessment',
    
    # Specialized models
    'OslomodellAssessment',
    'EnvironmentalAssessment',
    'TriageAssessment',
    
    # Aggregation
    'ComprehensiveAssessment',
    
    # Factories
    'MetadataFactory',
    'InputFactory',
    'AssessmentFactory'
]