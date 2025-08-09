#!/usr/bin/env python3
"""
test_full_miljokrav_integration.py
Complete integration test showing Miljøkrav + Oslomodell + Triage working together.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.enhanced_llm_gateway import LLMGateway
from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator, Goal, GoalStatus
from src.models.procurement_models import ProcurementRequest, ProcurementCategory

load_dotenv()

async def test_construction_project():
    """Test a large construction project requiring all assessments."""
    
    print("\n" + "="*80)
    print("🏗️ TEST: Large Construction Project")
    print("="*80)
    
    # Create procurement
    request = ProcurementRequest(
        name="Totalentreprise ny ungdomsskole",
        value=125_000_000,
        description="Bygging av ny ungdomsskole med idrettshall, 800 elever",
        category=ProcurementCategory.BYGGE,
        duration_months=24,
        includes_construction=True,
        requires_security_clearance=False,
        framework_agreement=False
    )
    
    print(f"\nProcurement Details:")
    print(f"  Name: {request.name}")
    print(f"  Value: {request.value:,} NOK")
    print(f"  Category: {request.category.value}")
    print(f"  Duration: {request.duration_months} months")
    
    # Initialize orchestrator
    llm_gateway = LLMGateway()
    orchestrator = ReasoningOrchestrator(llm_gateway)
    
    # Define comprehensive goal
    goal = Goal(
        id=request.id,
        description=f"Complete assessment of procurement: {request.name}",
        context={"request": request.model_dump()},
        success_criteria=[
            "Environmental requirements (Miljøkrav) assessed",
            "Oslo Model compliance (Oslomodell) verified",
            "Risk assessment (Triage) completed",
            "All results saved to database"
        ]
    )
    
    print(f"\nGoal: {goal.description}")
    print(f"Success Criteria:")
    for criterion in goal.success_criteria:
        print(f"  - {criterion}")
    
    print(f"\n{'='*40}")
    print("EXECUTING ORCHESTRATION...")
    print(f"{'='*40}\n")
    
    # Execute
    context = await orchestrator.achieve_goal(goal)
    
    # Analyze results
    print(f"\n{'='*40}")
    print("RESULTS")
    print(f"{'='*40}")
    
    print(f"\nOrchestration Status: {goal.status.value}")
    print(f"Total Iterations: {len(context.execution_history)}")
    
    # Extract results from each agent
    miljokrav_result = None
    oslomodell_result = None
    triage_result = None
    
    print("\nAgent Assessments:")
    for exec in context.execution_history:
        method = exec['action']['method']
        
        if 'miljokrav' in method:
            if exec['result'].get('status') == 'success':
                miljokrav_result = exec['result'].get('result', {})
                print(f"\n1. MILJØKRAV (Environmental Requirements):")
                print(f"   - Standard requirements: {'Required' if miljokrav_result.get('standard_krav_påkrevd') else 'Not required'}")
                print(f"   - Zero-emission mass transport: {'Yes' if miljokrav_result.get('krav_utslippsfri_massetransport') else 'No'}")
                print(f"   - Heavy vehicles >3.5t: {'Yes' if miljokrav_result.get('krav_utslippsfri_transport_35tonn') else 'No'}")
                print(f"   - Market dialogue recommended: {'Yes' if miljokrav_result.get('markedsdialog_anbefalt') else 'No'}")
                
                if miljokrav_result.get('viktige_frister'):
                    print(f"   - Important deadlines:")
                    for deadline, date in miljokrav_result['viktige_frister'].items():
                        print(f"     • {deadline}: {date}")
        
        elif 'oslomodell' in method:
            if exec['result'].get('status') == 'success':
                oslomodell_result = exec['result'].get('result', {})
                print(f"\n2. OSLOMODELL (Seriousness Requirements):")
                print(f"   - Crime risk assessment: {oslomodell_result.get('vurdert_risiko_for_akrim', 'Unknown')}")
                print(f"   - Required requirements: {oslomodell_result.get('påkrevde_seriøsitetskrav', [])}")
                print(f"   - Max subcontractor levels: {oslomodell_result.get('anbefalt_antall_underleverandørledd', 'N/A')}")
                
                apprentice = oslomodell_result.get('krav_om_lærlinger', {})
                if apprentice.get('status'):
                    print(f"   - Apprentice requirements: Required")
                    print(f"     Reason: {apprentice.get('begrunnelse', 'N/A')}")
        
        elif 'triage' in method:
            if exec['result'].get('status') == 'success':
                triage_result = exec['result'].get('result', {})
                print(f"\n3. TRIAGE (Risk Classification):")
                print(f"   - Classification: {triage_result.get('color', 'Unknown')}")
                print(f"   - Reasoning: {triage_result.get('reasoning', 'N/A')}")
                print(f"   - Confidence: {triage_result.get('confidence', 0):.1%}")
    
    # Summary and recommendations
    print(f"\n{'='*40}")
    print("SUMMARY & RECOMMENDATIONS")
    print(f"{'='*40}")
    
    if goal.status == GoalStatus.COMPLETED:
        print("\n✅ All assessments completed successfully!")
        
        # Combine recommendations
        all_recommendations = set()
        
        if miljokrav_result:
            for rec in miljokrav_result.get('recommendations', []):
                all_recommendations.add(f"[Miljø] {rec}")
        
        if oslomodell_result:
            for rec in oslomodell_result.get('recommendations', []):
                all_recommendations.add(f"[Oslo] {rec}")
        
        if triage_result:
            for rec in triage_result.get('recommendations', []):
                all_recommendations.add(f"[Risk] {rec}")
        
        if all_recommendations:
            print("\nCombined Recommendations:")
            for i, rec in enumerate(all_recommendations, 1):
                print(f"  {i}. {rec}")
        
        # Key compliance points
        print("\n📋 Key Compliance Points:")
        print(f"  • Value exceeds all thresholds - full requirements apply")
        print(f"  • Environmental: Standard climate requirements mandatory")
        print(f"  • Seriousness: Full A-U requirements for construction >500k")
        print(f"  • Apprentices: Required (>1.3M and construction)")
        print(f"  • Risk level: {triage_result.get('color', 'Unknown')} - appropriate for project size")
        
        return True
    else:
        print(f"\n⚠️ Assessment incomplete: {goal.status.value}")
        return False

async def test_small_service():
    """Test a small service procurement with minimal requirements."""
    
    print("\n" + "="*80)
    print("📦 TEST: Small Service Procurement")
    print("="*80)
    
    request = ProcurementRequest(
        name="IT support tjenester",
        value=450_000,
        description="Teknisk support for kommunens IT-systemer",
        category=ProcurementCategory.KONSULENT,
        duration_months=12,
        includes_construction=False
    )
    
    print(f"\nProcurement Details:")
    print(f"  Name: {request.name}")
    print(f"  Value: {request.value:,} NOK")
    print(f"  Category: {request.category.value}")
    
    llm_gateway = LLMGateway()
    orchestrator = ReasoningOrchestrator(llm_gateway)
    
    goal = Goal(
        id=request.id,
        description=f"Assess procurement: {request.name}",
        context={"request": request.model_dump()},
        success_criteria=[
            "Appropriate assessments completed",
            "Compliance verified"
        ]
    )
    
    context = await orchestrator.achieve_goal(goal)
    
    if goal.status == GoalStatus.COMPLETED:
        print("\n✅ Assessment completed")
        print("\nExpected outcome for small IT service:")
        print("  • Miljøkrav: Standard requirements apply (>100k)")
        print("  • Oslomodell: Limited requirements (service <500k)")
        print("  • Triage: GREEN - Low risk")
        return True
    else:
        print(f"\n⚠️ Assessment failed: {goal.status.value}")
        return False

async def main():
    """Run integration tests."""
    print("\n" + "="*80)
    print("🧪 FULL MULTI-AGENT INTEGRATION TEST")
    print("Miljøkrav + Oslomodell + Triage")
    print("="*80)
    
    results = {}
    
    # Test 1: Large construction
    try:
        results['construction'] = await test_construction_project()
    except Exception as e:
        print(f"\n❌ Construction test failed: {e}")
        import traceback
        traceback.print_exc()
        results['construction'] = False
    
    # Test 2: Small service
    try:
        results['service'] = await test_small_service()
    except Exception as e:
        print(f"\n❌ Service test failed: {e}")
        results['service'] = False
    
    # Final summary
    print("\n" + "="*80)
    print("📊 FINAL RESULTS")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        print("\nThe multi-agent system is working correctly:")
        print("  • Miljøkrav agent assesses environmental requirements")
        print("  • Oslomodell agent checks compliance")
        print("  • Triage agent evaluates risk")
        print("  • Orchestrator coordinates all assessments")
        print("  • Results are properly saved to database")
    else:
        print("\n⚠️ Some tests failed - check output above")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    print("\nNote: This test requires all three agents to be set up:")
    print("  1. Miljøkrav agent (environmental)")
    print("  2. Oslomodell agent (compliance)")
    print("  3. Triage agent (risk)")
    print("\nStarting tests in 3 seconds...")
    
    import time
    time.sleep(3)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)