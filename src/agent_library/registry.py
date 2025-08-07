# src/agent_library/registry.py
"""
Registry system with dependency injection for automatic agent discovery.
"""
from typing import Dict, Any, Optional, Type, List
import structlog
import json

logger = structlog.get_logger()

# Global registry for all tools and agents
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}

def register_tool(
    name: str, 
    service_type: str, 
    metadata: Dict[str, Any], 
    dependencies: Optional[List[str]] = None
):
    """
    Decorator that automatically registers an agent or tool with dependency injection support.
    
    Args:
        name: Method name for RPC calls (e.g., "agent.run_triage")
        service_type: "specialist_agent" or "automated_tool"
        metadata: Description, input/output schemas, etc.
        dependencies: List of required dependencies (e.g., ["gemini_gateway", "supabase_gateway"])
    
    Example:
        @register_tool(
            name="agent.run_triage",
            service_type="specialist_agent",
            metadata={"description": "Triage assessment"},
            dependencies=["gemini_gateway"]
        )
        class TriageAgent(BaseSpecialistAgent):
            ...
    """
    def decorator(cls):
        TOOL_REGISTRY[name] = {
            "class": cls,
            "service_type": service_type,
            "metadata": metadata,
            "method_name": name,
            "dependencies": dependencies or ["gemini_gateway"]  # Default dependency
        }
        
        # Add metadata to the class for introspection
        cls._tool_name = name
        cls._service_type = service_type
        cls._metadata = metadata
        cls._dependencies = dependencies or ["gemini_gateway"]
        
        logger.info("Tool registered", 
                   name=name, 
                   service_type=service_type, 
                   class_name=cls.__name__, 
                   dependencies=dependencies)
        return cls
    
    return decorator

def get_available_tools() -> Dict[str, Dict[str, Any]]:
    """Return all registered tools with their metadata."""
    return TOOL_REGISTRY.copy()

def get_tool_class(method_name: str) -> Optional[Type]:
    """Get the class for a specific tool method."""
    tool_info = TOOL_REGISTRY.get(method_name)
    return tool_info["class"] if tool_info else None

def create_agent_from_registry(
    method_name: str, 
    dependency_container: Dict[str, Any]
) -> Any:
    """
    Factory function to create agent instances using dependency injection.
    
    Args:
        method_name: The registered method name (e.g., "agent.run_triage")
        dependency_container: Dict with available dependencies
        
    Returns:
        Instantiated agent with all required dependencies injected
    
    Example:
        container = {
            "gemini_gateway": gemini_instance,
            "supabase_gateway": supabase_instance
        }
        agent = create_agent_from_registry("agent.run_oslomodell", container)
    """
    tool_info = TOOL_REGISTRY.get(method_name)
    if not tool_info:
        raise ValueError(f"Tool not found in registry: {method_name}")
    
    AgentClass = tool_info["class"]
    required_deps = tool_info.get("dependencies", ["gemini_gateway"])
    
    # Build constructor arguments from dependency container
    constructor_args = []
    missing_deps = []
    
    for dep_name in required_deps:
        if dep_name not in dependency_container:
            missing_deps.append(dep_name)
        else:
            constructor_args.append(dependency_container[dep_name])
    
    if missing_deps:
        raise ValueError(
            f"Missing required dependencies for {method_name}: {missing_deps}. "
            f"Available: {list(dependency_container.keys())}"
        )
    
    # Instantiate with correct dependencies
    agent_instance = AgentClass(*constructor_args)
    
    logger.info("Agent created via DI", 
               method=method_name, 
               dependencies=required_deps,
               class_name=AgentClass.__name__)
    
    return agent_instance

def generate_gateway_catalog_sql() -> str:
    """
    Generate SQL INSERT statements for gateway_service_catalog.
    This syncs the code registry with the database.
    """
    statements = []
    
    for method_name, tool_info in TOOL_REGISTRY.items():
        # Determine service name based on method pattern
        service_name = method_name.split('.')[0]  # "agent" or "tool"
        function_key = method_name.split('.', 1)[1] if '.' in method_name else method_name
        
        # Build SQL function name
        if tool_info["service_type"] == "specialist_agent":
            sql_function_name = f"{tool_info['class'].__name__}.execute"
        else:  # automated_tool
            sql_function_name = f"{tool_info['class'].__name__}.execute"
        
        # Convert metadata to JSON string
        metadata_json = json.dumps(tool_info["metadata"])
        
        statement = f"""
INSERT INTO gateway_service_catalog 
    (service_name, service_type, function_key, sql_function_name, function_metadata)
VALUES 
    ('{service_name}', '{tool_info["service_type"]}', '{function_key}', 
     '{sql_function_name}', '{metadata_json}'::jsonb)
ON CONFLICT (service_name, function_key) DO UPDATE SET 
    sql_function_name = EXCLUDED.sql_function_name,
    function_metadata = EXCLUDED.function_metadata,
    is_active = true;"""
        
        statements.append(statement)
    
    return "\n".join(statements)

def generate_acl_config_sql(agent_id: str = "reasoning_orchestrator") -> str:
    """
    Generate SQL INSERT statements for gateway_acl_config.
    Grants the orchestrator access to all registered tools.
    """
    statements = []
    
    for method_name in TOOL_REGISTRY.keys():
        statement = f"""
INSERT INTO gateway_acl_config (agent_id, allowed_method)
VALUES ('{agent_id}', '{method_name}')
ON CONFLICT (agent_id, allowed_method) DO UPDATE SET
    is_active = true;"""
        statements.append(statement)
    
    return "\n".join(statements)