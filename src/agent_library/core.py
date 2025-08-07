# src/agent_library/core.py
"""
Core base classes for the Agent SDK.
Provides standardized interfaces for specialist agents and automated tools.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import structlog
from pydantic import ValidationError

logger = structlog.get_logger()

class BaseAutomatedTool(ABC):
    """Base class for all Level 4 (N4) deterministic tools."""
    
    def __init__(self):
        self.tool_name = getattr(self, '_tool_name', self.__class__.__name__)
        logger.info("Automated tool initialized", tool_name=self.tool_name)
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the deterministic operation."""
        pass
    
    def validate_input(self, params: Dict[str, Any]) -> bool:
        """Override to add custom input validation."""
        return True

class BaseSpecialistAgent(ABC):
    """Base class for all Level 3 (N3) specialist agents."""
    
    def __init__(self, *args):
        # First argument is always gemini_gateway by convention
        self.llm_gateway = args[0] if args else None
        
        # Store additional dependencies
        self.dependencies = args[1:] if len(args) > 1 else []
        
        self.agent_name = getattr(self, '_agent_name', self.__class__.__name__)
        logger.info("Specialist agent initialized", 
                   agent_name=self.agent_name, 
                   dep_count=len(self.dependencies))
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's cognitive process."""
        pass
    
    async def execute_with_validation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with automatic input/output validation."""
        # Input validation
        InputSchema = getattr(self, '_input_schema_class', None)
        if InputSchema:
            try:
                validated_params = InputSchema.model_validate(params)
                params = validated_params.model_dump()
                logger.debug("Input validation successful", agent=self.agent_name)
            except ValidationError as e:
                logger.error("Input validation failed", 
                           agent=self.agent_name, error=str(e))
                raise ValueError(f"Invalid input for {self.agent_name}: {e}")
        
        # Custom business logic validation
        if not await self.validate_input(params):
            raise ValueError(f"Business logic validation failed for {self.agent_name}")
        
        # Pre-execution hook
        params = await self.pre_execute_hook(params)
        
        # Execute main logic
        try:
            result = await self.execute(params)
        except Exception as e:
            logger.error("Agent execution failed", 
                       agent=self.agent_name, error=str(e), exc_info=True)
            # Return error in standardized format
            return {
                "status": "error",
                "error": str(e),
                "agent": self.agent_name
            }
        
        # Output validation
        OutputSchema = getattr(self, '_output_schema_class', None)
        if OutputSchema:
            try:
                validated_result = OutputSchema.model_validate(result)
                result = validated_result.model_dump()
                logger.debug("Output validation successful", agent=self.agent_name)
            except ValidationError as e:
                logger.warning("Agent produced invalid output", 
                            agent=self.agent_name, error=str(e))
                raise ValueError(f"Agent {self.agent_name} produced invalid output: {e}")
        
        # Post-execution hook
        result = await self.post_execute_hook(result)
        
        return result
    
    async def validate_input(self, params: Dict[str, Any]) -> bool:
        """Override to add custom business logic validation."""
        return True
    
    async def pre_execute_hook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Override for custom pre-processing."""
        return params
    
    async def post_execute_hook(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Override for custom post-processing."""
        return result