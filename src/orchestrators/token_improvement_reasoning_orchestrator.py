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
**VIKTIG REGEL FOR LAGRING:** Hvis du ser et felt i `CURRENT_STATE` som heter `[agent]_pending_save: true` (f.eks. `triage_pending_save: true`), er din neste oppgave å kalle den tilhørende lagringsfunksjonen (f.eks. `database.save_triage_result`). Du trenger ikke spesifisere parametere for lagring; systemet håndterer dette automatisk.
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
        """
        Utfører en planlagt handling med dynamisk håndtering for lagringsoperasjoner.
        """
        method = action.method
        params = action.parameters
        
        logger.info("Executing action", method=method, has_params=bool(params))

        try:
            is_save_method = False
            agent_name_key = None
            for agent_name, tool_info in TOOL_REGISTRY.items():
                if method == tool_info.get('save_method'):
                    is_save_method = True
                    agent_name_key = agent_name.replace("agent.run_", "")
                    break
            
            if is_save_method and agent_name_key:
                logger.info(f"Save method detected for '{agent_name_key}'. Overriding LLM parameters.")
                full_result_to_save = context.current_state.get(f"_temp_{agent_name_key}_result_for_saving")
                if not full_result_to_save:
                    raise ValueError(f"Result for '{agent_name_key}' not found in state, cannot save.")
                params = full_result_to_save

            if method.startswith("database."):
                result = await gateway.call(method, params)
            elif method.startswith("agent."):
                result = await self._call_specialist_agent(method, params)
            else:
                raise ValueError(f"Unknown method type: {method}")
                
            context.add_execution(action, {"status": "success", "result": result})
            return {"status": "success", "result": result}
                
        except Exception as e:
            logger.error("Action execution failed", method=action.method, error=str(e), exc_info=True)
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
        """
        Oppdaterer state dynamisk og token-effektivt basert på agentens metadata.
        """
        method = action.method
        action_result = result.get("result", {})
        if not isinstance(action_result, dict):
            context.current_state[f"{method}_result"] = action_result
            return

        context.current_state["last_action_status"] = "success"

        # Dynamisk håndtering for ALLE agent-kjøringer
        if method.startswith("agent.run_"):
            agent_name = method.replace("agent.run_", "")
            
            context.current_state[f"{agent_name}_completed"] = True
            context.current_state[f"{agent_name}_pending_save"] = True
            
            # Generisk destillering for å spare tokens:
            summary = {k: v for k, v in action_result.items() if not isinstance(v, (list, dict))}
            context.current_state[f"{agent_name}_summary"] = summary
            
            # Lagre det fulle resultatet midlertidig for neste 'save'-steg
            context.current_state[f"_temp_{agent_name}_result_for_saving"] = action_result

        # Dynamisk håndtering for ALLE lagrings-handlinger
        elif any(method == info.get('save_method') for info in TOOL_REGISTRY.values()):
            for agent_name_full, info in TOOL_REGISTRY.items():
                if method == info.get('save_method'):
                    agent_name = agent_name_full.replace("agent.run_", "")
                    context.current_state[f"{agent_name}_saved"] = True
                    context.current_state.pop(f"{agent_name}_pending_save", None)
                    context.current_state.pop(f"_temp_{agent_name}_result_for_saving", None)
                    context.current_state.pop(f"{agent_name}_summary", None)
                    break

        elif method == 'database.create_procurement':
            context.current_state["procurementId"] = action_result.get("procurementId")
            context.current_state["procurement_created"] = True
    
    def _summarize_executions(self, history: List[Dict[str, Any]]) -> str:
        """Summarize execution history."""
        if not history:
            return "No actions performed yet."
        
        # ENDRING: Vis kun de 3 siste handlingene, og kun de viktigste feltene
        summary_limit = 3 
        summary = []
        for entry in history[-summary_limit:]:
            action = entry.get("action", {})
            result = entry.get("result", {})
            status = "SUCCESS" if result.get("status") == "success" else "ERROR"
            
            # Inkluder kun det aller viktigste for å spare plass
            summary.append(f"- {action.get('method')} -> {status}")

        if len(history) > summary_limit:
            return f"Summary of the last {summary_limit} of {len(history)} actions:\n" + "\n".join(summary)
        
        return "Executed Actions:\n" + "\n".join(summary)
    
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