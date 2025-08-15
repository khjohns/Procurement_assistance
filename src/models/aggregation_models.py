# src/models/aggregation_models.py
"""
Models for orchestration and aggregation of assessments.
Used by the orchestrator to combine results from multiple agents.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from .base_models import BaseProcurementInput, Requirement
from .specialized_models import (
    OslomodellAssessment, EnvironmentalAssessment, 
    TriageAssessment, ProtocolOutput
)
from .enums import RiskLevel

# ==============================================================================
# ORCHESTRATION MODELS
# ==============================================================================

class AssessmentRequest(BaseModel):
    """Unified request for orchestrator."""
    
    procurement: BaseProcurementInput = Field(..., description="Procurement to assess")
    requested_assessments: List[str] = Field(
        default=["triage", "oslomodell", "environmental"],
        description="Which assessments to perform"
    )
    priority: str = Field(default="normal", description="Priority: low/normal/high/urgent")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    generate_protocol: bool = Field(default=True, description="Generate protocol after assessment")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class OrchestrationStep(BaseModel):
    """Single step in orchestration process."""
    
    step_number: int = Field(..., description="Step sequence number")
    agent_name: str = Field(..., description="Agent to execute")
    input_data: Dict[str, Any] = Field(..., description="Input for agent")
    depends_on: List[int] = Field(default_factory=list, description="Dependencies on other steps")
    timeout_seconds: int = Field(default=30, description="Timeout for step")
    retry_on_failure: bool = Field(default=True, description="Retry if fails")
    
class OrchestrationPlan(BaseModel):
    """Execution plan for assessment orchestration."""
    
    plan_id: str = Field(..., description="Unique plan ID")
    procurement_id: str = Field(..., description="Procurement being assessed")
    steps: List[OrchestrationStep] = Field(..., description="Execution steps")
    parallel_execution: bool = Field(default=True, description="Execute independent steps in parallel")
    created_at: datetime = Field(default_factory=datetime.now)

# ==============================================================================
# AGGREGATION MODELS
# ==============================================================================

class ComprehensiveAssessment(BaseModel):
    """Aggregated assessment from all agents."""
    
    # Request info
    request_id: str = Field(..., description="Original request ID")
    procurement: BaseProcurementInput = Field(..., description="Procurement details")
    
    # Individual assessments
    triage_assessment: Optional[TriageAssessment] = Field(None, description="Triage result")
    oslomodell_assessment: Optional[OslomodellAssessment] = Field(None, description="Oslomodell result")
    environmental_assessment: Optional[EnvironmentalAssessment] = Field(None, description="Environmental result")
    
    # Generated protocol
    protocol: Optional[ProtocolOutput] = Field(None, description="Generated protocol")
    
    # Aggregated results
    total_requirements: List[Requirement] = Field(default_factory=list, description="All requirements")
    overall_risk: RiskLevel = Field(default=RiskLevel.LOW, description="Overall risk level")
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall confidence")
    
    # Combined recommendations
    key_recommendations: List[str] = Field(default_factory=list, description="Key recommendations")
    critical_warnings: List[str] = Field(default_factory=list, description="Critical warnings")
    next_steps: List[str] = Field(default_factory=list, description="Recommended next steps")
    
    # Metadata
    completed_at: datetime = Field(default_factory=datetime.now)
    processing_time_ms: Optional[int] = Field(None, description="Total processing time")
    successful_assessments: List[str] = Field(default_factory=list, description="Completed assessments")
    failed_assessments: List[str] = Field(default_factory=list, description="Failed assessments")
    
    def aggregate_requirements(self) -> None:
        """Aggregate and deduplicate requirements from all assessments."""
        all_reqs = []
        
        if self.oslomodell_assessment:
            all_reqs.extend(self.oslomodell_assessment.required_requirements)
        
        if self.environmental_assessment:
            all_reqs.extend(self.environmental_assessment.applied_requirements)
        
        # Deduplicate by code
        unique = {req.code: req for req in all_reqs}
        self.total_requirements = list(unique.values())
    
    def calculate_overall_risk(self) -> None:
        """Calculate overall risk from all assessments."""
        risks = []
        
        if self.oslomodell_assessment:
            risks.extend([
                self.oslomodell_assessment.labor_risk_assessment,
                self.oslomodell_assessment.social_dumping_risk,
                self.oslomodell_assessment.corruption_risk,
                self.oslomodell_assessment.environment_risk
            ])
        
        if self.environmental_assessment:
            risks.extend([
                self.environmental_assessment.environmental_risk,
                self.environmental_assessment.climate_impact
            ])
        
        # Return highest risk
        risk_priority = {
            RiskLevel.CRITICAL: 4,
            RiskLevel.HIGH: 3,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 1,
            RiskLevel.NONE: 0
        }
        
        if risks:
            highest_risk = max(risks, key=lambda r: risk_priority.get(r, 0))
            self.overall_risk = highest_risk
    
    def calculate_overall_confidence(self) -> None:
        """Calculate weighted average confidence."""
        confidences = []
        
        if self.triage_assessment:
            confidences.append(self.triage_assessment.confidence_score)
        
        if self.oslomodell_assessment:
            confidences.append(self.oslomodell_assessment.confidence_score)
        
        if self.environmental_assessment:
            confidences.append(self.environmental_assessment.confidence_score)
        
        if confidences:
            self.overall_confidence = sum(confidences) / len(confidences)
    
    def aggregate_recommendations(self) -> None:
        """Combine and prioritize recommendations."""
        all_recommendations = []
        all_warnings = []
        
        # Collect from all assessments
        for assessment in [self.triage_assessment, self.oslomodell_assessment, self.environmental_assessment]:
            if assessment:
                all_recommendations.extend(assessment.recommendations)
                all_warnings.extend(assessment.warnings)
        
        # Deduplicate and prioritize
        self.key_recommendations = list(dict.fromkeys(all_recommendations))[:10]
        self.critical_warnings = list(dict.fromkeys(all_warnings))[:5]
        
        # Generate next steps based on assessments
        self.generate_next_steps()
    
    def generate_next_steps(self) -> None:
        """Generate actionable next steps based on assessments."""
        steps = []
        
        # Based on triage color
        if self.triage_assessment:
            if self.triage_assessment.color == "rød":
                steps.append("Gjennomfør full risikovurdering før videre arbeid")
            elif self.triage_assessment.color == "gul":
                steps.append("Vurder behov for markedsdialog")
        
        # Based on risk levels
        if self.overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            steps.append("Etabler risikoreduserende tiltak")
            steps.append("Vurder behov for ekstern bistand")
        
        # Based on requirements
        if len(self.total_requirements) > 10:
            steps.append("Utarbeid detaljert kravspesifikasjon")
        
        self.next_steps = steps
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ==============================================================================
# EXECUTION TRACKING MODELS
# ==============================================================================

class ExecutionLog(BaseModel):
    """Log entry for orchestration execution."""
    
    log_id: str = Field(..., description="Unique log ID")
    procurement_id: str = Field(..., description="Procurement ID")
    agent_name: str = Field(..., description="Agent that was executed")
    
    started_at: datetime = Field(..., description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    duration_ms: Optional[int] = Field(None, description="Execution duration")
    
    success: bool = Field(..., description="Whether execution succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retries")
    
    input_data: Dict[str, Any] = Field(..., description="Input provided")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Output received")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class OrchestrationSummary(BaseModel):
    """Summary of orchestration execution."""
    
    summary_id: str = Field(..., description="Unique summary ID")
    procurement_id: str = Field(..., description="Procurement ID")
    request_id: str = Field(..., description="Original request ID")
    
    total_agents_executed: int = Field(..., description="Total agents executed")
    successful_executions: int = Field(..., description="Successful executions")
    failed_executions: int = Field(..., description="Failed executions")
    
    total_duration_ms: int = Field(..., description="Total execution time")
    parallel_execution_used: bool = Field(..., description="Whether parallel execution was used")
    
    execution_logs: List[ExecutionLog] = Field(default_factory=list, description="Detailed logs")
    
    started_at: datetime = Field(..., description="Orchestration start time")
    completed_at: datetime = Field(..., description="Orchestration completion time")
    
    final_status: str = Field(..., description="Final status: success/partial/failed")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }