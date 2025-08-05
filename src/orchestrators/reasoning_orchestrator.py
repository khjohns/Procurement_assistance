# orchestrators/reasoning_orchestrator.py - Refaktorert til engelsk API
import asyncio
import json
import httpx
import structlog
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from src.tools.rpc_gateway_client import RPCGatewayClient
from src.tools.gemini_gateway import GeminiGateway

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
    
    def __init__(self, llm_gateway: GeminiGateway, 
                 agent_id: str = "reasoning_orchestrator",
                 gateway_url: str = "http://localhost:8000",
                 max_iterations: int = 10):
        self.llm_gateway = llm_gateway
        self.agent_id = agent_id
        self.gateway_url = gateway_url
        self.max_iterations = max_iterations
        logger.info("ReasoningOrchestrator initialized", 
                   agent_id=agent_id,
                   max_iterations=max_iterations)
    
    async def _discover_tools(self) -> List[Dict[str, Any]]:
        """Discovers available tools from gateway."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.gateway_url}/discover/{self.agent_id}")
            response.raise_for_status()
            data = response.json()
            return data.get("tools", [])

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
        """Calls specialist agent with English API."""
        # Import here to avoid circular dependencies
        from src.specialists.triage_agent import TriageAgent
        from src.specialists.protocol_generator import ProtocolGenerator
        from src.models.procurement_models import ProcurementRequest, TriageResult  # Refactored model names

        agent_map = {
            "agent.run_triage": TriageAgent,
            "agent.run_protocol_generation": ProtocolGenerator,
        }
        
        agent_class = agent_map.get(method)
        if not agent_class:
            raise ValueError(f"Unknown specialist agent method: {method}")
            
        # Create agent instance
        agent_instance = agent_class(self.llm_gateway)
        
        # Execute action with English API
        request_data = parameters.get("procurement")  # Changed from "request" to "procurement"
        if not request_data:
            raise ValueError("'procurement' parameter is missing for specialist agent call")
            
        request_obj = ProcurementRequest(**request_data)  # Refactored model name
        
        if method == "agent.run_triage":
            result = await agent_instance.assess_procurement(request_obj)  # English method name
            return result.model_dump()  # Return as dict
        elif method == "agent.run_protocol_generation":
            result = await agent_instance.generate_protocol(request_obj)
            return result.model_dump()  # Return as dict

        return None

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
        """Uses LLM to plan next action based on context with English API."""
        
        if not context.available_tools:
            logger.warning("No tools available for planning")
            return None
        
        active_tools = context.available_tools

        if not active_tools:
            logger.warning("No active tools available")
            return None
        
        # Build prompt for LLM
        tools_description = self._format_tools_for_llm(active_tools)
        execution_summary = self._summarize_execution_history(context.execution_history)
        
        # Simplified first action for testing - if no actions executed yet
        if len(context.execution_history) == 0 and "request" in context.current_state:
            # First action should be creating the procurement
            request_data = context.current_state.get("request", {})
            return Action(
                method="database.create_procurement",  # English method name
                parameters={
                    "name": request_data.get("name", ""),  # English parameter names
                    "value": request_data.get("value", 0),
                    "description": request_data.get("description", "")
                },
                reasoning="First step is to create the procurement case in the database",
                expected_outcome="A new procurement case created with unique ID"
            )
        
        prompt = f"""You are an intelligent orchestrator that should achieve the following goal:

    GOAL: {context.goal.description}

    SUCCESS CRITERIA:
    {json.dumps(context.goal.success_criteria, indent=2)}

    CURRENT STATE:
    {json.dumps(context.current_state, indent=2)}

    EXECUTED ACTIONS:
    {execution_summary}

    AVAILABLE TOOLS (ONLY THESE CAN BE USED):
    {tools_description}

    IMPORTANT: You can ONLY use the tools listed above. DO NOT suggest tools that are not in the list.
    Specifically: DO NOT suggest agent.run_triage or other agent.* methods unless they are in the list above.

    Based on the context, plan the best next action to achieve the goal.
    If the goal is already achieved or no action can be performed with available tools, return null.

    Use the ENGLISH API method names:
    - database.create_procurement (not opprett_anskaffelse)
    - database.save_triage_result (not lagre_triage_resultat)
    - database.set_procurement_status (not sett_status)
    - database.save_protocol (not lagre_protokoll)
    - database.log_execution (not log_orchestrator_execution)

    Parameter names should use camelCase:
    - procurementId (not request_id)
    - protocolContent (not protokoll_tekst)

    Respond in the following JSON format:
    {{
        "method": "service.function",
        "parameters": {{}},
        "reasoning": "Explanation of why this action is best",
        "expected_outcome": "What you expect to achieve"
    }}

    Or null if no action is needed.
    """
        
        try:
            response = await self.llm_gateway.generate(
                prompt=prompt,
                temperature=0.3,
                response_mime_type="application/json"
            )
            
            action_data = json.loads(response)
            if not action_data:
                return None
            
            # Validate that suggested method is actually available
            available_methods = [tool['method'] for tool in active_tools]
            if action_data.get("method") not in available_methods:
                logger.warning(f"LLM suggested unavailable method: {action_data.get('method')}")
                return None
                
            return Action(
                method=action_data["method"],
                parameters=action_data["parameters"],
                reasoning=action_data["reasoning"],
                expected_outcome=action_data["expected_outcome"]
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse LLM response", error=str(e))
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

            elif "triage" in action.method:
                context.current_state["triage_completed"] = True
                # action_result here is the result from TriageAgent directly
                context.current_state["triage_result"] = action_result
                context.current_state["triage_color"] = action_result.get("color")  # English field name

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
        """
        Checks if the goal is achieved based on success criteria.
        Enhanced to look at actually executed actions.
        """
        
        # Give LLM a clearer overview of what has been done
        execution_summary = self._summarize_execution_history(context.execution_history)
        
        prompt = f"""You are a precise auditor. Assess if the following goal is achieved, based on the list of EXECUTED ACTIONS.

    GOAL: {context.goal.description}

    SUCCESS CRITERIA:
    {json.dumps(context.goal.success_criteria, indent=2)}

    CURRENT STATE (this is only data available for NEXT action, not proof of what has been done):
    {json.dumps(context.current_state, indent=2)}

    EXECUTED ACTIONS (this is the final log of what has happened):
    {execution_summary}

    INSTRUCTIONS:
    Look at each success criterion. Check if a corresponding action exists in the 'EXECUTED ACTIONS' log.
    Be strict: If a criterion requires something to be saved, a "save_*" action must be in the log.
    If all criteria are covered by actions in the log, the goal is achieved.

    Respond ONLY in JSON format:
    {{
      "goal_achieved": true/false,
      "reasoning": "Brief explanation of the assessment, referencing missing actions if relevant.",
      "missing_criteria": ["A list of criteria not covered by executed actions."]
    }}
    """
        
        response_str = await self.llm_gateway.generate(
            prompt,
            model="gemini-2.5-flash",  # Use Flash for quick evaluations
            temperature=0.1,
            response_mime_type="application/json"
        )
        
        try:
            evaluation = json.loads(response_str)
            is_achieved = evaluation.get("goal_achieved", False)
            if not is_achieved:
                logger.info("Goal not yet achieved", 
                            reason=evaluation.get("reasoning"),
                            missing=evaluation.get("missing_criteria"))
            return is_achieved
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse goal completion check", response=response_str, error=str(e))
            return False
    
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