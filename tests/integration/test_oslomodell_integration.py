#!/usr/bin/env python3
"""
test_oslomodell_integration.py
Complete integration test for Oslomodell with RPC Gateway.
Tests all components: Knowledge base, Agent, Orchestration.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import json



from src.tools.enhanced_llm_gateway import LLMGateway
from src.tools.embedding_gateway import EmbeddingGateway
from src.tools.rpc_gateway_client import RPCGatewayClient
from src.orchestrators.reasoning_orchestrator import ReasoningOrchestrator, Goal, GoalStatus
from src.models.procurement_models import ProcurementRequest, ProcurementCategory

load_dotenv()

async def test_knowledge_base():
    """Test 1: Verify knowledge base is accessible."""
    print("\n📚 Test 1: Knowledge Base")
    print("-" * 40)
    
    async with RPCGatewayClient(
        agent_id="oslomodell_agent",
        gateway_url="http://localhost:8000"
    ) as client:
        
        # List documents
        result = await client.call("database.list_knowledge_documents", {})
        
        if result.get('status') == 'success':
            docs = result.get('documents', [])
            print(f"✅ Found {len(docs)} documents in knowledge base")
            for doc in docs:
                print(f"   - {doc['documentId']}: {doc['contentLength']} chars")
            return len(docs) >= 3
        else:
            print(f"❌ Failed to list documents: {result.get('message')}")
            return False

async def test_knowledge_search():
    """Test 2: Verify vector search works."""
    print("\n🔍 Test 2: Knowledge Search")
    print("-" * 40)
    
    embedding_gateway = EmbeddingGateway(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Generate test query embedding
    test_query = "seriøsitetskrav bygge anlegg over 500000"
    query_embedding = await embedding_gateway.create_embedding(
        text=test_query,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=1536
    )
    
    async with RPCGatewayClient(
        agent_id="oslomodell_agent",
        gateway_url="http://localhost:8000"
    ) as client:
        
        result = await client.call("database.search_knowledge_documents", {
            "queryEmbedding": query_embedding,
            "threshold": 0.5,
            "limit": 3,
            "metadataFilter": {}
        })
        
        if result.get('status') == 'success':
            docs = result.get('results', [])
            print(f"✅ Search returned {len(docs)} relevant documents")
            for doc in docs:
                print(f"   - {doc['documentId']}: similarity={doc['similarity']:.3f}")
            return len(docs) > 0
        else:
            print(f"❌ Search failed: {result.get('message')}")
            return False

async def test_oslomodell_agent():
    """Test 3: Test Oslomodell agent directly."""
    print("\n🏛️ Test 3: Oslomodell Agent")
    print("-" * 40)
    
    from src.specialists.oslomodell_agent import OslomodellAgent
    
    llm_gateway = LLMGateway()
    embedding_gateway = EmbeddingGateway(api_key=os.getenv("GEMINI_API_KEY"))
    
    agent = OslomodellAgent(llm_gateway, embedding_gateway)
    
    # Test procurement
    test_procurement = {
        "name": "Totalentreprise ny barnehage",
        "value": 15_000_000,
        "category": "bygge",
        "description": "Bygging av ny 4-avdelings barnehage",
        "duration_months": 12
    }
    
    print(f"Testing with: {test_procurement['name']}")
    print(f"Value: {test_procurement['value']:,} NOK")
    
    result = await agent.execute({"procurement": test_procurement})
    
    if result.get('vurdert_risiko_for_akrim'):
        print(f"✅ Risk assessment: {result['vurdert_risiko_for_akrim']}")
        print(f"   Requirements: {len(result.get('påkrevde_seriøsitetskrav', []))} krav")
        print(f"   Subcontractor levels: {result.get('anbefalt_antall_underleverandørledd')}")
        print(f"   Apprentices required: {result.get('krav_om_lærlinger', {}).get('status')}")
        return True
    else:
        print(f"❌ Agent failed: {result}")
        return False

async def test_full_orchestration():
    """Test 4: Full orchestration with Oslomodell."""
    print("\n🎭 Test 4: Full Orchestration")
    print("-" * 40)
    
    llm_gateway = LLMGateway()
    orchestrator = ReasoningOrchestrator(llm_gateway)
    
    # Create test procurement
    request = ProcurementRequest(
        name="Rammeavtale IT-konsulenter",
        value=8_000_000,
        description="4-årig rammeavtale for IT-konsulenter til digital transformasjon",
        category=ProcurementCategory.KONSULENT,
        duration_months=48,
        framework_agreement=True
    )
    
    print(f"Procurement: {request.name}")
    print(f"Value: {request.value:,} NOK")
    print(f"Category: {request.category.value}")
    
    # Define goal
    goal = Goal(
        id=request.id,
        description=f"Analyze procurement: {request.name}",
        context={"request": request.model_dump()},
        success_criteria=[
            "Oslomodell assessment completed",
            "Triage assessment completed",
            "Status updated in database"
        ]
    )
    
    # Execute
    context = await orchestrator.achieve_goal(goal)
    
    if goal.status == GoalStatus.COMPLETED:
        print(f"✅ Orchestration completed successfully")
        print(f"   Iterations: {len(context.execution_history)}")
        
        # Extract results
        for exec in context.execution_history:
            if exec['action']['method'] == 'agent.run_oslomodell':
                if exec['result'].get('status') == 'success':
                    oslo_result = exec['result']['result']
                    print(f"   Oslomodell: Risk={oslo_result.get('vurdert_risiko_for_akrim')}")
            
            elif exec['action']['method'] == 'agent.run_triage':
                if exec['result'].get('status') == 'success':
                    triage_result = exec['result']['result']
                    print(f"   Triage: Color={triage_result.get('color')}")
        
        return True
    else:
        print(f"❌ Orchestration failed: {goal.status.value}")
        return False

async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🧪 OSLOMODELL INTEGRATION TEST SUITE")
    print("="*60)
    
    results = {}
    
    # Test 1: Knowledge base
    try:
        results['knowledge_base'] = await test_knowledge_base()
    except Exception as e:
        print(f"❌ Exception: {e}")
        results['knowledge_base'] = False
    
    # Test 2: Search
    try:
        results['search'] = await test_knowledge_search()
    except Exception as e:
        print(f"❌ Exception: {e}")
        results['search'] = False
    
    # Test 3: Agent
    try:
        results['agent'] = await test_oslomodell_agent()
    except Exception as e:
        print(f"❌ Exception: {e}")
        results['agent'] = False
    
    # Test 4: Orchestration
    try:
        results['orchestration'] = await test_full_orchestration()
    except Exception as e:
        print(f"❌ Exception: {e}")
        results['orchestration'] = False
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST RESULTS")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s}: {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("⚠️ SOME TESTS FAILED - Check the output above")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)