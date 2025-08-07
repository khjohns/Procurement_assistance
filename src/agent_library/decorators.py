# src/agent_library/decorators.py
"""
Decorators for automatic schema validation and metadata generation.
"""
from typing import Dict, Any, Type
from pydantic import BaseModel

def with_input_schema(schema_class: Type[BaseModel]):
    """
    Decorator to attach input schema validation.
    
    Example:
        @with_input_schema(ProcurementRequest)
        class MyAgent(BaseSpecialistAgent):
            ...
    """
    def decorator(cls):
        cls._input_schema_class = schema_class
        return cls
    return decorator

def with_output_schema(schema_class: Type[BaseModel]):
    """
    Decorator to attach output schema validation.
    
    Example:
        @with_output_schema(TriageResult)
        class MyAgent(BaseSpecialistAgent):
            ...
    """
    def decorator(cls):
        cls._output_schema_class = schema_class
        return cls
    return decorator

def with_schemas(
    input_schema: Type[BaseModel] = None, 
    output_schema: Type[BaseModel] = None
):
    """
    Combined decorator for both input and output schemas.
    
    Example:
        @with_schemas(
            input_schema=ProcurementRequest,
            output_schema=TriageResult
        )
        class TriageAgent(BaseSpecialistAgent):
            ...
    """
    def decorator(cls):
        if input_schema:
            cls._input_schema_class = input_schema
        if output_schema:
            cls._output_schema_class = output_schema
        return cls
    return decorator

def build_metadata(
    description: str, 
    input_schema_class: Type[BaseModel] = None, 
    output_schema_class: Type[BaseModel] = None,
    additional_info: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Build standard metadata dict from Pydantic schemas.
    
    Args:
        description: Human-readable description of the tool
        input_schema_class: Pydantic model for input validation
        output_schema_class: Pydantic model for output validation
        additional_info: Any additional metadata
    
    Returns:
        Metadata dict compatible with gateway_service_catalog
    """
    metadata = {"description": description}
    
    if input_schema_class:
        metadata["input_schema"] = input_schema_class.model_json_schema()
    
    if output_schema_class:
        metadata["output_schema"] = output_schema_class.model_json_schema()
    
    if additional_info:
        metadata.update(additional_info)
    
    return metadata

def requires_dependencies(*dependency_names: str):
    """
    Decorator to explicitly declare required dependencies.
    Used for documentation and validation.
    
    Example:
        @requires_dependencies("gemini_gateway", "supabase_gateway")
        class OslomodellAgent(BaseSpecialistAgent):
            ...
    """
    def decorator(cls):
        cls._required_dependencies = dependency_names
        return cls
    return decorator