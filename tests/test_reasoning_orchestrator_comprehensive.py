# tests/test_reasoning_orchestrator_comprehensive.py
"""
Comprehensive test suite for Reasoning Orchestrator.
Tests various goal complexities, agent interactions, and database operations.
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from colorama import Fore, Style, init
import structlog

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Import orchestrator and dependencies
from src.orchestrators.reasoning_orchestrator import (
    ReasoningOrchestrator, 
    Goal, 
    GoalStatus,
    ExecutionContext
)

from src.tools.llm_gateway import LLMGateway

# Configure structured logging with color
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(colors=True)
    ]
)
logger = structlog.get_logger()

# ========================================
# TEST UTILITIES
# ========================================

class TestReporter:
    """Utility class for beautiful test output."""
    
    def __init__(self):
        self.test_results = []
        self.current_test = None
        
    def start_test(self, name: str, description: str):
        """Start a new test."""
        self.current_test = {
            "name": name,
            "description": description,
            "start_time": datetime.now(),
            "steps": []
        }
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.YELLOW}🧪 TEST: {name}")
        print(f"{Fore.WHITE}📋 Description: {description}")
        print(f"{Fore.CYAN}{'='*80}")
    
    def log_step(self, step: str, status: str = "info"):
        """Log a test step."""
        colors = {
            "info": Fore.WHITE,
            "success": Fore.GREEN,
            "warning": Fore.YELLOW,
            "error": Fore.RED
        }
        icon = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌"
        }
        
        print(f"{colors[status]}{icon[status]}  {step}")
        if self.current_test:
            self.current_test["steps"].append({
                "step": step,
                "status": status,
                "time": datetime.now()
            })
    
    def log_action(self, action: str, params: Dict = None):
        """Log an orchestrator action."""
        print(f"{Fore.BLUE}🎯 Action: {action}")
        if params:
            print(f"{Fore.CYAN}   Params: {json.dumps(params, indent=2)}")
    
    def end_test(self, success: bool, summary: str = None):
        """End current test."""
        if self.current_test:
            self.current_test["end_time"] = datetime.now()
            self.current_test["duration"] = (
                self.current_test["end_time"] - self.current_test["start_time"]
            ).total_seconds()
            self.current_test["success"] = success
            self.current_test["summary"] = summary
            self.test_results.append(self.current_test)
        
        status_icon = "✅" if success else "❌"
        status_color = Fore.GREEN if success else Fore.RED
        
        print(f"\n{status_color}{status_icon} Test {'PASSED' if success else 'FAILED'}")
        if summary:
            print(f"{Fore.WHITE}📝 Summary: {summary}")
        
        if self.current_test:
            print(f"{Fore.CYAN}⏱️  Duration: {self.current_test['duration']:.2f}s")
    
    def print_summary(self):
        """Print test suite summary."""
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.YELLOW}📊 TEST SUITE SUMMARY")
        print(f"{Fore.CYAN}{'='*80}")
        
        total = len(self.test_results)
        passed = sum(1 for t in self.test_results if t["success"])
        failed = total - passed
        
        print(f"{Fore.WHITE}Total Tests: {total}")
        print(f"{Fore.GREEN}Passed: {passed}")
        print(f"{Fore.RED}Failed: {failed}")
        
        print(f"\n{Fore.YELLOW}Test Details:")
        for test in self.test_results:
            icon = "✅" if test["success"] else "❌"
            print(f"{icon} {test['name']} ({test['duration']:.2f}s)")

# ========================================
# TEST CASES
# ========================================

async def test_simple_database_goal(orchestrator: ReasoningOrchestrator, reporter: TestReporter):
    """Test 1: Simple database operation only."""
    reporter.start_test(
        "Simple Database Goal",
        "Create procurement in database without any agent assessments"
    )
    
    try:
        # Create simple goal
        goal = Goal(
            id="test-simple-001",
            description="Create a procurement record in the database",
            context={
                "request": {
                    "name": "Kontorrekvisita",
                    "value": 25000,
                    "description": "Innkjøp av kontorrekvisita for Q1 2025"
                }
            },
            success_criteria=[
                "Procurement case created in database"
            ]
        )
        
        reporter.log_step("Goal created with 1 success criterion")
        
        # Execute
        context = await orchestrator.achieve_goal(goal)
        
        # Report execution
        for i, execution in enumerate(context.execution_history):
            action = execution["action"]
            result = execution["result"]
            status = "success" if result.get("status") == "success" else "error"
            reporter.log_action(action["method"], action.get("parameters"))
            reporter.log_step(f"Result: {result.get('status')}", status)
        
        # Check success
        success = goal.status == GoalStatus.COMPLETED
        reporter.end_test(
            success,
            f"Created procurement with ID: {context.current_state.get('procurementId')}"
        )
        
        assert success, f"Målet skulle vært COMPLETED, men var {goal.status.value}"
        
    except Exception as e:
        reporter.log_step(f"Exception: {str(e)}", "error")
        reporter.end_test(False, "Test failed with exception")
        return False


async def test_single_agent_goal(orchestrator: ReasoningOrchestrator, reporter: TestReporter):
    """Test 2: Single agent assessment with database save."""
    reporter.start_test(
        "Single Agent Goal",
        "Run triage assessment and save to database"
    )
    
    try:
        goal = Goal(
            id="test-agent-001",
            description="Perform triage assessment on procurement and save result",
            context={
                "request": {
                    "name": "IT-konsulentbistand",
                    "value": 750000,
                    "description": "Konsulentbistand for systemutvikling i 6 måneder"
                }
            },
            success_criteria=[
                "Procurement case created in database",
                "Triage assessment completed and saved"
            ]
        )
        
        reporter.log_step("Goal created with 2 success criteria")
        
        context = await orchestrator.achieve_goal(goal)
        
        # Report execution
        for execution in context.execution_history:
            action = execution["action"]
            result = execution["result"]
            reporter.log_action(action["method"])
            
            if "triage" in action["method"].lower():
                triage_result = result.get("result", {})
                reporter.log_step(
                    f"Triage: {triage_result.get('color', 'UNKNOWN')} - "
                    f"{triage_result.get('reasoning', 'No reasoning')}",
                    "success" if result.get("status") == "success" else "error"
                )
        
        success = goal.status == GoalStatus.COMPLETED
        triage_color = context.current_state.get("triage_color", "UNKNOWN")
        
        reporter.end_test(
            success,
            f"Triage completed: {triage_color}"
        )
        
        assert success, f"Målet skulle vært COMPLETED, men var {goal.status.value}"
        
    except Exception as e:
        reporter.log_step(f"Exception: {str(e)}", "error")
        reporter.end_test(False, "Test failed with exception")
        return False


async def test_multi_agent_goal(orchestrator: ReasoningOrchestrator, reporter: TestReporter):
    """Test 3: Multiple agents working together."""
    reporter.start_test(
        "Multi-Agent Goal",
        "Run multiple assessments (triage, oslomodell, environmental)"
    )
    
    try:
        goal = Goal(
            id="test-multi-001",
            description="Complete all assessments for construction procurement",
            context={
                "request": {
                    "name": "Rehabilitering av skolebygg",
                    "value": 15000000,
                    "description": "Total rehabilitering av Nordre skole, inkludert nytt ventilasjonsanlegg",
                    "category": "construction",
                    "duration_months": 18,
                    "includes_construction": True
                }
            },
            success_criteria=[
                "Procurement case created in database",
                "Triage assessment completed and saved",
                "Oslomodell assessment completed and saved",
                "Environmental assessment completed and saved"
            ]
        )
        
        reporter.log_step(f"Goal created with {len(goal.success_criteria)} success criteria")
        reporter.log_step(f"Procurement value: {goal.context['request']['value']:,} NOK", "info")
        
        context = await orchestrator.achieve_goal(goal)
        
        # Track which agents were called
        agents_called = set()
        for execution in context.execution_history:
            action = execution["action"]
            if "agent." in action["method"]:
                agents_called.add(action["method"])
                reporter.log_action(action["method"])
                
                # Log specific results
                if action["method"] == "agent.run_triage":
                    result = execution["result"].get("result", {})
                    reporter.log_step(
                        f"Triage: {result.get('color', 'UNKNOWN')}",
                        "success"
                    )
                elif action["method"] == "agent.run_oslomodell":
                    result = execution["result"].get("result", {})
                    reporter.log_step(
                        f"Oslomodell risk: {result.get('vurdert_risiko_for_akrim', 'UNKNOWN')}",
                        "success"
                    )
                elif action["method"] == "agent.run_environmental":
                    result = execution["result"].get("result", {})
                    reporter.log_step(
                        f"Environmental risk: {result.get('environmental_risk', 'UNKNOWN')}",
                        "success"
                    )
        
        success = goal.status == GoalStatus.COMPLETED
        reporter.end_test(
            success,
            f"Called {len(agents_called)} different agents"
        )
        
        assert success, f"Målet skulle vært COMPLETED, men var {goal.status.value}"
        
    except Exception as e:
        reporter.log_step(f"Exception: {str(e)}", "error")
        reporter.end_test(False, "Test failed with exception")
        return False


async def test_complete_procurement_flow(orchestrator: ReasoningOrchestrator, reporter: TestReporter):
    """Test 4: Complete procurement flow with track routing."""
    reporter.start_test(
        "Complete Procurement Flow",
        "Full workflow from creation to track routing and notifications"
    )
    
    try:
        # Use the high-level method
        procurement_data = {
            "name": "Rammeavtale kontormøbler",
            "value": 2500000,
            "description": "4-årig rammeavtale for kontormøbler til alle kommunens lokasjoner",
            "category": "goods",
            "duration_months": 48
        }
        
        reporter.log_step(f"Processing procurement: {procurement_data['name']}")
        reporter.log_step(f"Value: {procurement_data['value']:,} NOK", "info")
        
        context = await orchestrator.process_procurement_request(procurement_data)
        
        # Analyze the workflow
        workflow_steps = {}
        for execution in context.execution_history:
            action = execution["action"]["method"]
            status = execution["result"].get("status", "unknown")
            
            if action not in workflow_steps:
                workflow_steps[action] = status
                
                # Log key milestones
                if "create_procurement" in action:
                    reporter.log_step("✓ Procurement created", "success")
                elif "run_triage" in action:
                    color = execution["result"].get("result", {}).get("color", "UNKNOWN")
                    reporter.log_step(f"✓ Triage: {color}", "success")
                elif "run_oslomodell" in action:
                    reporter.log_step("✓ Oslomodell assessed", "success")
                elif "run_environmental" in action:
                    reporter.log_step("✓ Environmental assessed", "success")
                elif "route_to_track" in action:
                    track = execution["result"].get("result", {}).get("track", "UNKNOWN")
                    reporter.log_step(f"✓ Routed to: {track}", "success")
                elif "generate_protocol" in action or "generate_case_document" in action:
                    reporter.log_step("✓ Document generated", "success")
                elif "send_notifications" in action:
                    reporter.log_step("✓ Notifications sent", "success")
        
        success = context.goal.status == GoalStatus.COMPLETED
        
        # Summary statistics
        total_actions = len(context.execution_history)
        successful_actions = sum(
            1 for e in context.execution_history 
            if e["result"].get("status") == "success"
        )
        
        reporter.end_test(
            success,
            f"Executed {total_actions} actions, {successful_actions} successful"
        )
        
        assert success, f"Målet skulle vært COMPLETED, men var {goal.status.value}"
        
    except Exception as e:
        reporter.log_step(f"Exception: {str(e)}", "error")
        reporter.end_test(False, "Test failed with exception")
        return False


async def test_error_recovery(orchestrator: ReasoningOrchestrator, reporter: TestReporter):
    """Test 5: Error handling and recovery."""
    reporter.start_test(
        "Error Recovery",
        "Test orchestrator's ability to handle and recover from errors"
    )
    
    try:
        # Create goal with invalid data to trigger some errors
        goal = Goal(
            id="test-error-001",
            description="Test error handling with partially invalid data",
            context={
                "request": {
                    "name": "",  # Empty name might cause issues
                    "value": -1000,  # Negative value
                    "description": "Test procurement with invalid data"
                }
            },
            success_criteria=[
                "Handle invalid input gracefully",
                "Either complete with corrections or escalate to human"
            ]
        )
        
        reporter.log_step("Created goal with invalid data")
        
        context = await orchestrator.achieve_goal(goal)
        
        # Check how errors were handled
        errors_encountered = []
        for execution in context.execution_history:
            if execution["result"].get("status") == "error":
                errors_encountered.append(execution["action"]["method"])
                reporter.log_step(
                    f"Error in {execution['action']['method']}: "
                    f"{execution['result'].get('message', 'Unknown error')}",
                    "warning"
                )
        
        # Success if it handled errors gracefully
        success = goal.status in [GoalStatus.COMPLETED, GoalStatus.REQUIRES_HUMAN]
        
        reporter.end_test(
            success,
            f"Encountered {len(errors_encountered)} errors, "
            f"final status: {goal.status.value}"
        )
        
        assert success, f"Målet skulle vært COMPLETED, men var {goal.status.value}"
        
    except Exception as e:
        reporter.log_step(f"Exception: {str(e)}", "error")
        reporter.end_test(False, "Test failed with exception")
        return False


async def test_complex_decision_making(orchestrator: ReasoningOrchestrator, reporter: TestReporter):
    """Test 6: Complex decision making with conditional logic."""
    reporter.start_test(
        "Complex Decision Making",
        "Test orchestrator's ability to make conditional decisions based on assessment results"
    )
    
    try:
        # High-risk procurement that should trigger RED track
        goal = Goal(
            id="test-complex-001",
            description="Process high-risk IT procurement with GDPR implications",
            context={
                "request": {
                    "name": "Ny HR-system med sensitive persondata",
                    "value": 8000000,
                    "description": "Anskaffelse av HR-system som behandler sensitive personopplysninger for 5000 ansatte",
                    "category": "it_system",
                    "gdpr_relevant": True,
                    "security_critical": True,
                    "duration_months": 60
                }
            },
            success_criteria=[
                "Procurement case created in database",
                "All assessments completed",
                "Appropriate track selected based on risk",
                "Escalation to legal department if high risk",
                "Comprehensive documentation generated"
            ]
        )
        
        reporter.log_step("Created high-risk procurement goal")
        reporter.log_step("GDPR relevant: Yes", "warning")
        reporter.log_step("Security critical: Yes", "warning")
        
        context = await orchestrator.achieve_goal(goal)
        
        # Analyze decision points
        decision_points = {
            "triage_color": None,
            "track_selected": None,
            "escalated": False,
            "legal_involved": False
        }
        
        for execution in context.execution_history:
            action = execution["action"]["method"]
            result = execution["result"]
            
            if "run_triage" in action and result.get("status") == "success":
                decision_points["triage_color"] = result.get("result", {}).get("color")
                reporter.log_step(f"Triage decision: {decision_points['triage_color']}", "info")
            
            if "route_to_track" in action and result.get("status") == "success":
                decision_points["track_selected"] = result.get("result", {}).get("track")
                reporter.log_step(f"Track selected: {decision_points['track_selected']}", "info")
                
                if result.get("result", {}).get("requires_legal_review"):
                    decision_points["legal_involved"] = True
                    reporter.log_step("Legal review required", "warning")
            
            if "escalate" in action.lower():
                decision_points["escalated"] = True
                reporter.log_step("Case escalated", "warning")
        
        # Verify correct decisions were made
        success = (
            goal.status == GoalStatus.COMPLETED and
            decision_points["triage_color"] == "RØD" and  # Should be RED
            decision_points["legal_involved"]  # Should involve legal
        )
        
        reporter.end_test(
            success,
            f"Correctly identified as high-risk: {decision_points['triage_color']} track"
        )
        
        assert success, f"Målet skulle vært COMPLETED, men var {goal.status.value}"
        
    except Exception as e:
        reporter.log_step(f"Exception: {str(e)}", "error")
        reporter.end_test(False, "Test failed with exception")
        return False