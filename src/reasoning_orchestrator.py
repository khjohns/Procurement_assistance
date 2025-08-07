import asyncio
import json
import httpx
import structlog
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field # ENDRING: Importer BaseModel og Field

from src.tools.rpc_gateway_client import RPCGatewayClient
from src.tools.enhanced_llm_gateway import LLMGateway  # NY import
from src.agent_library.registry import TOOL_REGISTRY, create_agent_from_registry

# Import alle agenter
import src.specialists.triage_agent

logger = structlog.get_logger()

class GoalStatus(Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"

@dataclass
class Goal:
    """Represents a goal the orchestrator should achieve."""
    id: str
    description: str
    context: Dict[str, Any]
    status: GoalStatus = GoalStatus.NOT_STARTED
    success_criteria: List[str] = None
    
    def __post_init__(self):
        if self.success_criteria is None:
            self.success_criteria = []

@dataclass
class Action:
    """Represents an action the orchestrator can perform."""
    method: str  # e.g. "database.save_triage_result" (English API)
    parameters: Dict[str, Any]
    reasoning: str
    expected_outcome: str

@dataclass
class ExecutionContext:
    """Holds context throughout the execution."""
    goal: Goal
    available_tools: List[Dict[str, Any]]
    execution_history: List[Dict[str, Any]]
    current_state: Dict[str, Any]
    
    def add_execution(self, action: Action, result: Dict[str, Any]):
        """Logs an executed action."""
        self.execution_history.append({
            "action": {
                "method": action.method,
                "parameters": action.parameters,
                "reasoning": action.reasoning
            },
            "result": result,
            "timestamp": asyncio.get_event_loop().time()
        })

class ReasoningOrchestrator:
    """
    A dynamic orchestrator that reasons through the best course of action
    to achieve a given goal using tools discovered via the gateway.
    """
    def __init__(self, 
                 llm_gateway: LLMGateway,  # ENDRE: Type hint
                 agent_id: str = "reasoning_orchestrator",
                 gateway_url: str = "http://localhost:8000",
                 max_iterations: int = 10):
        
        self.llm_gateway = llm_gateway
        self.agent_id = agent_id
        self.gateway_url = gateway_url
        self.max_iterations = max_iterations
        
        self.dependency_container = {
            "llm_gateway": self.llm_gateway,
            # Legg til andre dependencies etter behov
        }
        
        logger.info("ReasoningOrchestrator initialized", 
                   agent_id=agent_id,
                   llm_type="enhanced",
                   registered_tools=list(TOOL_REGISTRY.keys()))
    
    async def _discover_tools(self) -> List[Dict[str, Any]]:
        """
        Your existing discovery method remains the same.
        Database is still the single source of truth at runtime.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.gateway_url}/discover/{self.agent_id}")
            response.raise_for_status()
            data = response.json()
            tools = data.get("tools", [])
            
            # Log which tools are SDK-enabled
            sdk_tools = [t for t in tools if t['method'] in TOOL_REGISTRY]
            legacy_tools = [t for t in tools if t['method'] not in TOOL_REGISTRY]
            
            if sdk_tools:
                logger.info("SDK-enabled tools discovered", 
                          count=len(sdk_tools),
                          tools=[t['method'] for t in sdk_tools])
            
            if legacy_tools:
                logger.warning("Legacy tools still in use", 
                             count=len(legacy_tools),
                             tools=[t['method'] for t in legacy_tools])
            
            return tools

    async def _execute_action(self, gateway: RPCGatewayClient, 
                             action: Action, 
                             context: ExecutionContext) -> Dict[str, Any]:
        """Executes a planned action."""
        logger.info("Executing action", 
                   method=action.method,
                   parameters=action.parameters)
        
        try:
            # Differentiate between database calls and agent calls
            if action.method.startswith("database."):
                # Direct RPC call to database
                result = await gateway.call(action.method, action.parameters)
            
            elif action.method.startswith("agent."):
                # Call to specialist agent
                result = await self._call_specialist_agent(action.method, action.parameters)
            
            else:
                raise ValueError(f"Unknown method type: {action.method}")
            
            # Log successful action to history
            context.add_execution(action, {"status": "success", "result": result})
            return {"status": "success", "result": result}
            
        except Exception as e:
            logger.error("Action execution failed",
                        method=action.method,
                        error=str(e),
                        exc_info=True)
            
            error_result = {"status": "error", "message": str(e)}
            context.add_execution(action, error_result)
            return error_result

    async def _call_specialist_agent(self, method: str, 
                                   parameters: Dict[str, Any]) -> Any:
        """
        UPDATED METHOD: Now uses SDK registry with dependency injection.
        This completely replaces the old hardcoded agent_map approach.
        """
        logger.info("Calling specialist agent via SDK", 
                   method=method,
                   has_registry_entry=method in TOOL_REGISTRY)
        
        # Phase 1: Try SDK registry first (preferred)
        if method in TOOL_REGISTRY:
            try:
                # Use SDK factory to create agent with correct dependencies
                agent_instance = create_agent_from_registry(
                    method, 
                    self.dependency_container
                )
                
                # Execute with automatic validation
                result = await agent_instance.execute_with_validation(parameters)
                
                logger.info("SDK agent executed successfully", 
                           method=method, 
                           agent_class=agent_instance.__class__.__name__)
                
                return result
                
            except Exception as e:
                logger.error("SDK agent execution failed", 
                           method=method, 
                           error=str(e), 
                           exc_info=True)
                # During migration, you might want to fall back to legacy
                # Once stable, just raise the exception
                raise
        
        # Phase 2 (Migration): Fallback to legacy for non-migrated agents
        # Remove this section once all agents use SDK
        legacy_map = {
            # Keep old agents here temporarily during migration
            # "agent.run_protocol_generation": ProtocolGenerator,
        }
        
        if method in legacy_map:
            logger.warning("Using legacy agent (not yet migrated to SDK)", 
                         method=method)
            
            # Old implementation (to be removed)
            from src.specialists.protocol_generator import ProtocolGenerator
            from src.models.procurement_models import ProcurementRequest
            
            AgentClass = legacy_map[method]
            agent_instance = AgentClass(self.llm_gateway)
            
            # Call legacy method
            request_data = parameters.get("procurement", parameters)
            request_obj = ProcurementRequest(**request_data)
            
            if method == "agent.run_protocol_generation":
                result = await agent_instance.generate_protocol(request_obj)
                return result.model_dump()
        
        # No implementation found
        raise ValueError(f"Method not found in SDK or legacy systems: {method}")

    async def achieve_goal(self, goal: Goal) -> ExecutionContext:
        """
        Main method that drives the reasoning loop to achieve a goal.
        """
        logger.info("Starting goal achievement process",
                    goal_id=goal.id,
                    goal_description=goal.description)

        tools = await self._discover_tools()
        logger.info("Discovered tools", tool_count=len(tools))

        usable_tools = [tool for tool in tools
                        if tool.get('service_type') in ['postgres_rpc', 'specialist_agent']]

        logger.info("Usable tools", tool_count=len(usable_tools))

        context = ExecutionContext(
            goal=goal,
            available_tools=usable_tools,
            execution_history=[],
            current_state=goal.context.copy()
        )

        async with RPCGatewayClient(
            agent_id=self.agent_id,
            gateway_url=self.gateway_url
        ) as gateway:

            iteration = 0
            while iteration < self.max_iterations and goal.status not in [
                GoalStatus.COMPLETED,
                GoalStatus.FAILED,
                GoalStatus.REQUIRES_HUMAN
            ]:
                iteration += 1
                logger.info("Reasoning iteration",
                            iteration=iteration,
                            current_status=goal.status.value)

                action = await self._plan_next_action(context)

                if not action:
                    logger.warning("No further action planned by LLM.")
                    if not await self._check_goal_completion(context):
                        goal.status = GoalStatus.REQUIRES_HUMAN
                    break

                # Execute action using refactored method
                result_wrapper = await self._execute_action(gateway, action, context)
                
                # Update state based on result (if successful)
                if result_wrapper and result_wrapper.get("status") == "success":
                    await self._evaluate_result(action, result_wrapper, context)
                
                # Check if goal is achieved after action
                if await self._check_goal_completion(context):
                    goal.status = GoalStatus.COMPLETED
                    logger.info("Goal achieved!", goal_id=goal.id)
                    break

            # Handle end state
            if goal.status not in [GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.REQUIRES_HUMAN]:
                if iteration >= self.max_iterations:
                    logger.warning("Max iterations reached", goal_id=goal.id)
                    goal.status = GoalStatus.FAILED
                else:
                    goal.status = GoalStatus.REQUIRES_HUMAN

        # Log at the end
        try:
            await self._log_orchestration(context)
        except Exception as e:
            logger.warning("Failed to log orchestration", error=str(e))

        return context

    async def _plan_next_action(self, context: ExecutionContext) -> Optional[Action]:
        """OPPDATERT: Bruker enhanced LLM med purpose."""
        
        if not context.available_tools:
            logger.warning("No tools available for planning")
            return None
        
        # Bygg prompt
        tools_description = self._format_tools_for_llm(context.available_tools)
        execution_summary = self._summarize_execution_history(context.execution_history)
        
        prompt = f"""You are an intelligent orchestrator achieving this goal:

    GOAL: {context.goal.description}

    SUCCESS CRITERIA:
    {json.dumps(context.goal.success_criteria, indent=2)}

    CURRENT STATE:
    {json.dumps(context.current_state, indent=2)}

    EXECUTED ACTIONS:
    {execution_summary}

    AVAILABLE TOOLS:
    {tools_description}

    First step is to create the procurement case in the database.
    Plan the best next action to achieve the goal.
    If the goal is already achieved or no action needed, return null.

    Respond in JSON format:
    {{
        "method": "service.function",
        "parameters": {{}},
        "reasoning": "Why this action is best",
        "expected_outcome": "What you expect"
    }}
    """
        
        try:
            # ENDRE: Bruk generate_structured med purpose
            response = await self.llm_gateway.generate_structured(
                prompt=prompt,
                response_schema={
                    "type": "object",
                    "properties": {
                        "method": {"type": "string"},
                        "parameters": {"type": "object"},
                        "reasoning": {"type": "string"},
                        "expected_outcome": {"type": "string"}
                    }
                },
                purpose="complex_reasoning",  # Orkestrering krever dyp analyse
                temperature=0.3
            )
            
            if not response or response.get("error"):
                return None
                
            return Action(
                method=response["method"],
                parameters=response["parameters"],
                reasoning=response["reasoning"],
                expected_outcome=response["expected_outcome"]
            )
            
        except Exception as e:
            logger.error("Failed to plan action", error=str(e))
            return None
    
    async def _evaluate_result(self, action: Action,
                               result: Dict[str, Any],
                               context: ExecutionContext):
        """Evaluates the result of an action and updates context."""
        logger.info("Evaluating action result",
                    action_method=action.method,
                    result_status=result.get("status"))

        # Update current_state based on result
        if result.get("status") == "success":
            action_result = result.get("result", {})
            
            # Specific handling based on method (English API)
            if action.method == 'database.create_procurement':
                # Extract procurementId and make it easily accessible in state
                if isinstance(action_result, dict) and action_result.get("status") == "success":
                    created_id = action_result.get("procurementId")  # camelCase
                    if created_id:
                        context.current_state["procurementId"] = created_id
                        logger.info("Extracted and stored procurementId in context", procurement_id=created_id)

            # ENDRING 1: Legg til et flagg når triage er fullført, men ikke lagret
            elif action.method == 'agent.run_triage':
                context.current_state["triage_completed"] = True
                context.current_state["triage_result"] = action_result
                context.current_state["triage_color"] = action_result.get("color")
                # Her er nøkkelen: et eksplisitt flagg
                context.current_state["triage_result_pending_save"] = True
                logger.info("Triage result is now pending save.")

            # ENDRING 2: Legg til en handler for når lagringen faktisk skjer
            elif action.method == 'database.save_triage_result':
                context.current_state["triage_saved"] = True
                # Fjern flagget, siden handlingen er utført
                if "triage_result_pending_save" in context.current_state:
                    del context.current_state["triage_result_pending_save"]
                logger.info("Triage result has been successfully saved.")

            elif "protocol" in action.method:
                context.current_state["protocol_generated"] = True
                if isinstance(action_result, dict):
                     context.current_state["protocolId"] = action_result.get("protocolId")  # camelCase

            elif "status" in action.method:
                context.current_state["status_updated"] = True
                context.current_state["current_status"] = action.parameters.get("status")

        # General update to log last action
        context.current_state["last_action"] = action.method
        context.current_state["last_result"] = result
    
    async def _check_goal_completion(self, context: ExecutionContext) -> bool:
        """OPPDATERT: Sjekk måloppnåelse med enhanced LLM."""
        
        execution_summary = self._summarize_execution_history(context.execution_history)
        
        prompt = f"""Assess if the following goal is achieved:

    GOAL: {context.goal.description}

    SUCCESS CRITERIA:
    {json.dumps(context.goal.success_criteria, indent=2)}

    CURRENT STATE:
    {json.dumps(context.current_state, indent=2)}

    EXECUTED ACTIONS:
    {execution_summary}

    Respond ONLY in JSON:
    {{
        "goal_achieved": true/false,
        "reasoning": "Brief explanation",
        "missing_criteria": ["List of unmet criteria"]
    }}
    """
        
        # ENDRE: Bruk fast_evaluation for rask sjekk
        result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "goal_achieved": {"type": "boolean"},
                    "reasoning": {"type": "string"},
                    "missing_criteria": {"type": "array", "items": {"type": "string"}}
                }
            },
            purpose="fast_evaluation",  # Rask evaluering
            temperature=0.1
        )
        
        return result.get("goal_achieved", False)
    
    def _format_tools_for_llm(self, tools: List[Dict[str, Any]]) -> str:
        """Formats tools for LLM understanding."""
        formatted_tools = []
        for tool in tools:
            formatted_tools.append(f"""
- Method: {tool['method']}
  Description: {tool.get('description', 'No description')}
  Input: {json.dumps(tool.get('input_schema', {}), indent=2)}
  Output: {json.dumps(tool.get('output_schema', {}), indent=2)}
""")
        return "\n".join(formatted_tools)
    
    def _summarize_execution_history(self, history: List[Dict[str, Any]]) -> str:
        """Creates a concise summary of executed actions."""
        if not history:
            return "No actions performed yet."
        
        summary = []
        for i, entry in enumerate(history[-5:]):  # Show only last 5 actions
            action = entry["action"]
            result = entry["result"]
            status = "✓" if result.get("status") == "success" else "✗"
            summary.append(f"{i+1}. {status} {action['method']} - {action['reasoning']}")
        
        return "\n".join(summary)
    
    async def _log_orchestration(self, context: ExecutionContext):
        """Logs orchestration history to database using English API."""
        try:
            async with RPCGatewayClient(
                agent_id=self.agent_id,
                gateway_url=self.gateway_url
            ) as gateway:
                await gateway.call("database.log_execution", {  # English method name
                    "procurementId": context.goal.id,  # camelCase parameter
                    "goalDescription": context.goal.description,  # camelCase
                    "status": context.goal.status.value,
                    "iterations": len(context.execution_history),
                    "finalState": context.current_state,  # camelCase
                    "executionHistory": context.execution_history,  # camelCase
                    "agentId": self.agent_id  # camelCase
                })
        except Exception as e:
            logger.error("Failed to log orchestration", error=str(e))

    # Convenience method for processing procurement requests
    async def process_procurement_request(self, procurement_request: Dict[str, Any]) -> ExecutionContext:
        """
        High-level method to process a complete procurement request.
        Creates appropriate goal and success criteria.
        """
        goal = Goal(
            id=str(uuid.uuid4()),
            description="Process complete procurement case from request to protocol",
            context={"request": procurement_request},
            success_criteria=[
                "Procurement case created in database",
                "Triage assessment completed and saved", 
                "Protocol generated and saved",
                "Final status updated"
            ]
        )
        
        return await self.achieve_goal(goal)

    # Legacy compatibility method (for gradual migration)
    async def process_procurement(self, request) -> Dict[str, Any]:
        """
        Legacy-compatible method that wraps the new reasoning approach.
        Maintains backward compatibility during migration.
        """
        logger.info("Processing procurement via legacy interface", 
                   request_name=getattr(request, 'name', 'Unknown'))
        
        # Convert legacy request to new format
        procurement_data = {
            "name": getattr(request, 'name', ''),
            "value": getattr(request, 'value', 0),
            "description": getattr(request, 'description', '')
        }
        
        # Process using new reasoning orchestrator
        context = await self.process_procurement_request(procurement_data)
        
        # Convert result back to legacy format
        return {
            "status": "completed" if context.goal.status == GoalStatus.COMPLETED else "failed",
            "procurement_id": context.current_state.get("procurementId"),
            "triage": context.current_state.get("triage_result", {}),
            "protocol_id": context.current_state.get("protocolId"),
            "execution_history": context.execution_history,
            "iterations": len(context.execution_history)
        }