# src/orchestrators/reasoning_orchestrator.py
"""
Enhanced Reasoning Orchestrator with full SDK integration and improved reasoning.
No legacy code, uses dependency injection and enhanced prompts.
"""
import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import httpx
import structlog

from src.tools.rpc_gateway_client import RPCGatewayClient
from src.tools.llm_gateway import LLMGateway

from src.tools.embedding_gateway import EmbeddingGateway
import os

from src.agent_library.registry import TOOL_REGISTRY, create_agent_from_registry
from src.models.procurement_models import ComprehensiveAssessment

# Import alle agenter
import src.specialists.triage_agent
import src.specialists.oslomodel_agent
import src.specialists.environmental_agent

from pydantic import BaseModel, Field

logger = structlog.get_logger()

# Pydantic-modell for planen som LLM skal generere
class ActionPlan(BaseModel):
    method: str = Field(..., description="Metoden som skal kalles, f.eks. 'database.create_procurement'")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parametere for metoden")
    reasoning: str = Field(..., description="Kort begrunnelse for hvorfor denne handlingen ble valgt")
    expected_outcome: str = Field(..., description="Forventet resultat av handlingen")

# Pydantic-modell for resultatet av målsjekken
class GoalCompletionCheck(BaseModel):
    all_criteria_met: bool = Field(..., description="Om alle suksesskriterier er møtt")
    unmet_criteria: List[str] = Field(default_factory=list, description="En liste over kriterier som ikke er møtt")
    reasoning: str = Field(..., description="Kort begrunnelse for konklusjonen")

class GoalStatus(Enum):
    """Status of a goal in the reasoning process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_HUMAN = "requires_human"

@dataclass
class Goal:
    """Represents a goal to be achieved."""
    id: str
    description: str
    context: Dict[str, Any]
    success_criteria: List[str]
    status: GoalStatus = GoalStatus.PENDING

@dataclass
class Action:
    """Represents a planned action."""
    method: str
    parameters: Dict[str, Any]
    reasoning: str
    expected_outcome: str

@dataclass
class ExecutionContext:
    """Maintains state throughout goal achievement."""
    goal: Goal
    available_tools: List[Dict[str, Any]]
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    current_state: Dict[str, Any] = field(default_factory=dict)
    
    def add_execution(self, action: Action, result: Dict[str, Any]):
        """Add an executed action to history."""
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
    Dynamic orchestrator using enhanced reasoning and full SDK integration.
    Coordinates specialist agents to achieve procurement processing goals.
    """
    
    def __init__(self, 
                 llm_gateway: LLMGateway,
                 agent_id: str = "reasoning_orchestrator",
                 gateway_url: str = "http://localhost:8000",
                 max_iterations: int = 15):
        
        self.llm_gateway = llm_gateway
        self.agent_id = agent_id
        self.gateway_url = gateway_url
        self.max_iterations = max_iterations

        
        self.dependency_container = {
            "llm_gateway": self.llm_gateway,
            "embedding_gateway": 
            EmbeddingGateway(api_key=os.getenv("GEMINI_API_KEY"))
            }
        
        logger.info("ReasoningOrchestrator initialized", 
                   agent_id=agent_id,
                   llm_type="enhanced",
                   registered_tools=list(TOOL_REGISTRY.keys()))
    
    async def _discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools from gateway."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.gateway_url}/discover/{self.agent_id}")
                response.raise_for_status()
                data = response.json()
                tools = data.get("tools", [])
                
                sdk_tools = [t for t in tools if t['method'] in TOOL_REGISTRY]
                logger.info("Tools discovered", 
                          total=len(tools),
                          sdk_enabled=len(sdk_tools))
                
                return tools
        except Exception as e:
            logger.error("Tool discovery failed", error=str(e))
            return []
    
    async def achieve_goal(self, goal: Goal) -> ExecutionContext:
        """Main reasoning loop to achieve a goal."""
        logger.info("Starting goal achievement",
                   goal_id=goal.id,
                   goal_description=goal.description)
        
        tools = await self._discover_tools()
        usable_tools = [tool for tool in tools
                        if tool.get('service_type') in ['postgres_rpc', 'specialist_agent']]
        
        context = ExecutionContext(
            goal=goal,
            available_tools=usable_tools,
            execution_history=[],
            current_state=goal.context.copy()
        )
        
        goal.status = GoalStatus.IN_PROGRESS
        
        async with RPCGatewayClient(
            agent_id=self.agent_id,
            gateway_url=self.gateway_url
        ) as gateway:
            
            iteration = 0
            while iteration < self.max_iterations and goal.status == GoalStatus.IN_PROGRESS:
                iteration += 1
                logger.info("Reasoning iteration", 
                          iteration=iteration,
                          state_keys=list(context.current_state.keys()))
                
                # Plan next action
                action = await self._plan_next_action(context)
                
                if not action:
                    logger.warning("No action planned")
                    if not await self._check_goal_completion(context):
                        goal.status = GoalStatus.REQUIRES_HUMAN
                    break
                
                # Execute action
                result = await self._execute_action(gateway, action, context)
                
                # Update state
                if result and result.get("status") == "success":
                    await self._update_state(action, result, context)
                
                # Check goal completion
                if await self._check_goal_completion(context):
                    goal.status = GoalStatus.COMPLETED
                    logger.info("Goal achieved!", goal_id=goal.id)
                    break
            
            # Handle terminal states
            if goal.status == GoalStatus.IN_PROGRESS:
                if iteration >= self.max_iterations:
                    logger.warning("Max iterations reached")
                    goal.status = GoalStatus.FAILED
                else:
                    goal.status = GoalStatus.REQUIRES_HUMAN
        
        # Log orchestration
        await self._log_orchestration(context)
        
        return context
    
    async def _plan_next_action(self, context: ExecutionContext) -> Optional[Action]:
        """Enhanced action planning with improved prompt."""
        tools_description = self._format_tools_for_llm(context.available_tools)
        
        execution_summary = self._summarize_executions(context.execution_history)
        
        prompt = f"""Du er en metodisk AI-orkestrator. Din oppgave er å analysere en situasjon og planlegge nøyaktig ett neste steg for å nå et mål. Følg disse instruksjonene slavisk:

1. **Analyser Målet:** Forstå hva sluttresultatet skal være.
2. **Analyser Datagrunnlaget:** Se på `INITIAL_DATA` for den opprinnelige konteksten og `CURRENT_STATE` for resultater av tidligere handlinger.
3. **Vurder Verktøy:** Se på listen over `AVAILABLE_TOOLS` og deres beskrivelser.
4. **Velg Neste Handling:** Velg det *eneste* verktøyet som er det mest logiske neste steget.
5. **Fyll ut Parametre:** Hent all nødvendig data for verktøyets parametere fra `INITIAL_DATA` eller `CURRENT_STATE`. Dette er kritisk.
6. **Formuler Resonnement:** Forklar kort hvorfor du valgte akkurat dette verktøyet.
7. **Svar KUN med JSON:** Din respons må være et rent JSON-objekt.

<GOAL>
{context.goal.description}
</GOAL>

<SUCCESS_CRITERIA>
{json.dumps(context.goal.success_criteria, indent=2)}
</SUCCESS_CRITERIA>

<INITIAL_DATA>
{json.dumps(context.goal.context, indent=2)}
</INITIAL_DATA>

<CURRENT_STATE>
{json.dumps(context.current_state, indent=2)}
</CURRENT_STATE>

<AVAILABLE_TOOLS>
{tools_description}
</AVAILABLE_TOOLS>

<EXECUTED_ACTIONS>
{execution_summary}
</EXECUTED_ACTIONS>

EKSEMPEL på riktig svar hvis første steg:
{{
  "method": "database.create_procurement",
  "parameters": {{
    "name": "[hent fra INITIAL_DATA]",
    "value": [hent fra INITIAL_DATA],
    "description": "[hent fra INITIAL_DATA]"
  }},
  "reasoning": "Første steg er å opprette anskaffelsessaken i databasen",
  "expected_outcome": "Procurement ID returnert"
}}

Svar nå KUN med JSON-objektet for neste handling."""

        try:
            action_data = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema=ActionPlan.model_json_schema(), # Bruk Pydantic-modellen
            purpose="action_planning",
            temperature=0.3
        )
            
            if not action_data.get("method"):
                return None
            
            return Action(
                method=action_data["method"],
                parameters=action_data.get("parameters", {}),
                reasoning=action_data.get("reasoning", ""),
                expected_outcome=action_data.get("expected_outcome", "")
            )
            
        except Exception as e:
            logger.error("Action planning failed", error=str(e))
            return None
    
    async def _check_goal_completion(self, context: ExecutionContext) -> bool:
        """Enhanced goal completion check with strict criteria matching."""
        prompt = f"""Din oppgave er å vurdere om et mål er fullført ved å sammenligne suksesskriteriene med den nåværende tilstanden.

1. Les hvert enkelt punkt i `<SUCCESS_CRITERIA>`.
2. For hvert kriterium, sjekk om `<CURRENT_STATE>` inneholder bevis for at det er oppfylt.
   - Vær streng: `triage_completed: true` er ikke det samme som `triage_saved: true`. Se etter eksakte bevis.
3. Konkluder om **alle** kriteriene er oppfylt.
4. Svar KUN med et JSON-objekt.

<GOAL>
{context.goal.description}
</GOAL>

<SUCCESS_CRITERIA>
{json.dumps(context.goal.success_criteria, indent=2)}
</SUCCESS_CRITERIA>

<CURRENT_STATE>
{json.dumps(context.current_state, indent=2)}
</CURRENT_STATE>

Svar med JSON:
{{
  "all_criteria_met": true/false,
  "unmet_criteria": ["kriterium som ikke er oppfylt", ...],
  "reasoning": "Kort forklaring"
}}"""

        try:
            result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema=GoalCompletionCheck.model_json_schema(), # Bruk Pydantic-modellen
            purpose="goal_evaluation",
            temperature=0.1
            )
            
            return result.get("all_criteria_met", False)
            
        except Exception as e:
            logger.error("Goal completion check failed", error=str(e))
            return False
    
    def _format_tools_for_llm(self, tools: List[Dict[str, Any]]) -> str:
        """Formats tools for LLM understanding, including schemas."""
        formatted_tools = []
        for tool in tools:
            # Hent metadata. For agenter ligger det ofte i tool['metadata']
            metadata = tool.get('metadata', tool)
            
            formatted_tools.append(
    f"""- Method: {tool['method']}
      Description: {metadata.get('description', 'No description')}
      Input Schema: {json.dumps(metadata.get('input_schema', {}), indent=2)}
      Output Schema: {json.dumps(metadata.get('output_schema', {}), indent=2)}"""
            )
        return "\n".join(formatted_tools)
    

    async def _execute_action(self, gateway: RPCGatewayClient, 
                             action: Action, 
                             context: ExecutionContext) -> Dict[str, Any]:
        """Execute a planned action."""
        logger.info("Executing action", 
                   method=action.method,
                   has_params=bool(action.parameters))
        
        try:
            if action.method.startswith("database."):
                if action.method == 'database.save_triage_result':
                    # Overstyr LLM-planen! Hent det ekte resultatet fra minnet.
                    triage_result_data = context.current_state.get("triage_result")
                    if not triage_result_data:
                        raise ValueError("Triage result not found in state, cannot save.")
                    
                    # Bygg de korrekte parameterne basert på Pydantic-modellen
                    params = {
                        "procurementId": context.current_state.get("procurementId"),
                        "resultId": triage_result_data.get("procurement_id"), # Eller en annen unik ID
                        "color": triage_result_data.get("color"),
                        "reasoning": triage_result_data.get("reasoning"),
                        "confidence": triage_result_data.get("confidence")
                        # Legg til andre felter som backenden din forventer
                    }
                    result = await gateway.call(action.method, params)
                else:
                    # Standard databasekall for alle andre metoder
                    result = await gateway.call(action.method, action.parameters)
                # Direct database RPC call
                result = await gateway.call(action.method, action.parameters)
                
            elif action.method.startswith("agent."):
                # Specialist agent call via SDK
                result = await self._call_specialist_agent(action.method, action.parameters)
                
            else:
                raise ValueError(f"Unknown method type: {action.method}")
            
            # Log to history
            context.add_execution(action, {"status": "success", "result": result})
            return {"status": "success", "result": result}
            
        except Exception as e:
            logger.error("Action execution failed", 
                        method=action.method,
                        error=str(e))
            
            error_result = {"status": "error", "message": str(e)}
            context.add_execution(action, error_result)
            return error_result
    
    async def _call_specialist_agent(self, method: str, 
                                   parameters: Dict[str, Any]) -> Any:
        """Call specialist agent using SDK with dependency injection."""
        if method not in TOOL_REGISTRY:
            raise ValueError(f"Method not found in SDK registry: {method}")
        
        try:
            # Create agent instance with dependencies
            agent_instance = create_agent_from_registry(
                method,
                self.dependency_container
            )
            
            # Execute with validation
            result = await agent_instance.execute_with_validation(parameters)
            
            logger.info("SDK agent executed successfully",
                       method=method,
                       agent_class=agent_instance.__class__.__name__)
            
            return result
            
        except Exception as e:
            logger.error("SDK agent execution failed",
                        method=method,
                        error=str(e))
            raise
    
    async def _update_state(self, action: Action, result: Dict[str, Any], 
                          context: ExecutionContext):
        """Update context state based on action results."""
        action_result = result.get("result", {})
        
        # Handle different action types
        if action.method == 'database.create_procurement':
            if isinstance(action_result, dict) and action_result.get("status") == "success":
                context.current_state["procurementId"] = action_result.get("procurementId")
                context.current_state["procurement_created"] = True
        
        elif action.method == 'agent.run_triage':
            context.current_state["triage_completed"] = True
            context.current_state["triage_result"] = action_result
            context.current_state["triage_color"] = action_result.get("color")
            context.current_state["triage_pending_save"] = True
        
        elif action.method == 'database.save_triage_result':
            context.current_state["triage_saved"] = True
            context.current_state.pop("triage_pending_save", None)
        
        elif action.method == 'agent.run_oslomodell':
            context.current_state["oslomodell_completed"] = True
            context.current_state["oslomodell_result"] = action_result
            context.current_state["oslomodell_pending_save"] = True
        
        elif action.method == 'database.save_oslomodell_assessment':
            context.current_state["oslomodell_saved"] = True
            context.current_state.pop("oslomodell_pending_save", None)
        
        elif action.method == 'agent.run_environmental':
            context.current_state["environmental_completed"] = True
            context.current_state["environmental_result"] = action_result
            context.current_state["environmental_pending_save"] = True
        
        elif action.method == 'database.save_environmental_assessment':
            context.current_state["environmental_saved"] = True
            context.current_state.pop("environmental_pending_save", None)
        
        elif action.method == 'agent.route_to_track':
            context.current_state["track_routed"] = True
            context.current_state["selected_track"] = action_result.get("track")
            context.current_state["track_actions"] = action_result.get("actions", [])
        
        elif action.method == 'agent.generate_protocol':
            context.current_state["protocol_generated"] = True
            context.current_state["protocol_result"] = action_result
        
        elif action.method == 'agent.generate_case_document':
            context.current_state["case_document_generated"] = True
            context.current_state["case_document_result"] = action_result
        
        elif action.method == 'agent.send_notifications':
            context.current_state["notifications_sent"] = True
            context.current_state["notification_results"] = action_result
        
        elif action.method == 'database.save_comprehensive_assessment':
            context.current_state["comprehensive_assessment_saved"] = True
        
        # Always update last action
        context.current_state["last_action"] = action.method
        context.current_state["last_result"] = result
    
    def _summarize_executions(self, history: List[Dict[str, Any]]) -> str:
        """Summarize execution history."""
        if not history:
            return "No actions performed yet."
        
        summary = []
        for i, entry in enumerate(history[-5:]):  # Last 5 actions
            action = entry["action"]
            result = entry["result"]
            status = "✓" if result.get("status") == "success" else "✗"
            summary.append(f"{i+1}. {status} {action['method']}: {action['reasoning']}")
        
        return "\n".join(summary)
    
    async def _log_orchestration(self, context: ExecutionContext):
        """Log orchestration to database."""
        try:
            async with RPCGatewayClient(
                agent_id=self.agent_id,
                gateway_url=self.gateway_url
            ) as gateway:
                await gateway.call("database.log_execution", {
                    "procurementId": context.goal.id,
                    "goalDescription": context.goal.description,
                    "status": context.goal.status.value,
                    "iterations": len(context.execution_history),
                    "finalState": context.current_state,
                    "executionHistory": context.execution_history,
                    "agentId": self.agent_id
                })
        except Exception as e:
            logger.error("Failed to log orchestration", error=str(e))
    
    async def process_procurement_request(self, procurement_data: Dict[str, Any]) -> ExecutionContext:
        """
        High-level method to process complete procurement with all assessments.
        Creates comprehensive assessment workflow.
        """
        goal = Goal(
            id=str(uuid.uuid4()),
            description="Complete procurement assessment with all required evaluations and route to appropriate track",
            context={"request": procurement_data},
            success_criteria=[
                "Procurement case created in database",
                "Oslomodell assessment completed and saved",
                "Environmental assessment completed and saved",
                "Triage assessment completed and saved",
                "Case routed to appropriate track based on triage color",
                "Track-specific action completed (protocol or case document)",
                "Notifications sent to relevant parties",
                "Comprehensive assessment saved"
            ]
        )
        
        return await self.achieve_goal(goal)