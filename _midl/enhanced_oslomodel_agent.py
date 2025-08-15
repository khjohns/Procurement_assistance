# enhanced_oslomodel_agent_detailed.py

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from enum import Enum
import asyncio
from datetime import datetime

# ==============================================================================
# START: DUMMY-OBJEKTER FOR KJØRBARHET
# Forutsetter at disse modellene finnes i dine faktiske moduler.
# Dette er en sammenslåing av klasser fra procurement_models.py og procurement-models-adjustments.py
# ==============================================================================

class BaseModel:
    def __init__(self, **kwargs):
        # Enkel Pydantic-lignende init
        self.__dict__.update(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self, indent=None, ensure_ascii=False):
        # Forenklet versjon av Pydantic's model_dump
        def convert(obj):
            if isinstance(obj, BaseModel):
                return obj.model_dump()
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, (list, tuple)):
                return [convert(i) for i in obj]
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            return obj
        return convert(self.__dict__)

    @classmethod
    def model_validate(cls, obj):
        return cls(**obj)

# --- Enums ---
class ProcurementCategory(str, Enum):
    BYGGE_OG_ANLEGG = "bygge- og anlegg"
    TJENESTE = "tjeneste"
    VARE = "vare"
    RENHOLD = "renhold"
    IKT = "ikt"

class AssessmentStrategy(str, Enum):
    HYBRID_SEARCH = "hybrid_search"

# --- Modeller fra procurement-models-adjustments.py ---
class ChunkReference(BaseModel):
    pass

class RequirementWithMetadata(BaseModel):
    pass

class AssessmentMetadata(BaseModel):
    pass

class EnhancedOslomodellAssessmentResult(BaseModel):
    pass

# --- Hovedinputmodell fra procurement_models.py ---
class ProcurementRequest(BaseModel):
    id: str
    name: str
    value: int
    category: ProcurementCategory
    description: Optional[str] = ""
    duration_months: int = 0
    involves_construction: bool = False


# ==============================================================================
# SLUTT: DUMMY-OBJEKTER
# ==============================================================================


class EnhancedOslomodelAgent:
    """
    An ENHANCED Oslomodell agent that uses rich metadata for its core logic
    and produces a highly detailed assessment result for evaluation.
    """

    def __init__(self, llm_gateway=None, embedding_gateway=None, rpc_gateway_client=None):
        self.llm_gateway = llm_gateway
        self.embedding_gateway = embedding_gateway
        self.rpc_client = rpc_gateway_client

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the assessment with a retrieve -> evaluate -> generate workflow.
        """
        procurement = ProcurementRequest.model_validate(params.get("procurement", {}))
        print(f"🚀 Starting ENHANCED Oslomodell assessment for: {procurement.name}")

        start_time = datetime.now()

        # 1. Retrieve all potentially relevant chunks from the knowledge base
        retrieved_chunks = await self._multi_strategy_retrieval(procurement)
        print(f"🔍 Retrieved {len(retrieved_chunks)} potentially relevant chunks.")

        # 2. Evaluate which of the retrieved chunks are *actually* applicable
        applicable_chunks, reasoning_trace = self._get_applicable_chunks(procurement, retrieved_chunks)
        print(f"✅ Found {len(applicable_chunks)} applicable rules.")

        # 3. Generate the final, detailed assessment
        assessment = await self._generate_detailed_assessment(
            procurement,
            applicable_chunks,
            retrieved_chunks,
            reasoning_trace,
            start_time
        )

        print(f"🏁 Enhanced Oslomodell assessment completed for {procurement.name}.")
        return assessment.model_dump()

    def _get_applicable_chunks(self, procurement: ProcurementRequest, all_chunks: List[Dict[str, Any]]) -> (List[Dict[str, Any]], List[str]):
        """
        Iterates through chunks, returns those where conditions are met, and provides a reasoning trace.
        """
        applicable_chunks = []
        reasoning_trace = ["Initialising rule evaluation..."]
        for chunk in all_chunks:
            conditions = chunk.get('conditions', [])
            if not conditions:
                continue

            chunk_is_applicable = True
            for cond in conditions:
                condition_met = self._evaluate_condition(procurement, cond)
                if not condition_met:
                    chunk_is_applicable = False
                    reasoning_trace.append(f"Rule '{chunk['title']}': SKIPPED. Condition not met: {cond['description']}")
                    break # No need to check other conditions for this chunk
            
            if chunk_is_applicable:
                applicable_chunks.append(chunk)
                reasoning_trace.append(f"Rule '{chunk['title']}': APPLIED. All conditions met.")
        
        return applicable_chunks, reasoning_trace

    def _evaluate_condition(self, procurement: ProcurementRequest, condition: Dict[str, Any]) -> bool:
        """
        Evaluates a single, structured condition against the procurement data.
        """
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')

        try:
            if field == 'contractValue':
                proc_value = procurement.value
                if operator == '>=': return proc_value >= value
                if operator == '<=': return proc_value <= value
                if operator == 'between': return value[0] <= proc_value <= value[1]

            elif field == 'procurementCategory':
                proc_cat = procurement.category.value
                if operator == 'in': return proc_cat in value
                if operator == 'not in': return proc_cat not in value
        
        except (TypeError, KeyError, IndexError, AttributeError) as e:
            print(f"⚠️ Warning: Condition evaluation failed for condition {condition}. Error: {e}")
            return False
        
        return False

    async def _generate_detailed_assessment(
        self,
        procurement: ProcurementRequest,
        applicable_chunks: List[Dict[str, Any]],
        retrieved_chunks: List[Dict[str, Any]],
        reasoning_trace: List[str],
        start_time: datetime
    ) -> EnhancedOslomodellAssessmentResult:
        """
        Generates the final, detailed assessment object.
        This function simulates a powerful LLM call that structures the final output.
        """
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        all_requirement_codes = self._get_all_requirement_codes(applicable_chunks)
        
        # --- Mock LLM Reasoning ---
        risk = "høy" if procurement.value >= 1000000 else "moderat" if procurement.value >= 500000 else "lav"
        sub_levels = 0 if risk == "høy" else 1 if risk == "moderat" else 2
        
        # --- Build Detailed Models ---
        
        chunk_references = [
            ChunkReference(
                chunk_id=c['chunk_id'],
                section_number=c.get('section_number'),
                title=c['title'],
                relevance_score=0.95 if c in applicable_chunks else 0.6, # Mock score
                similarity_score=0.88 if c in applicable_chunks else 0.5, # Mock score
                chunk_level=c['chunk_level'],
                requirement_codes_found=c['requirement_codes']
            ) for c in retrieved_chunks
        ]
        
        assessment_metadata = AssessmentMetadata(
            retrieval_strategy=AssessmentStrategy.HYBRID_SEARCH,
            chunks_retrieved=len(retrieved_chunks),
            chunks_used=len(applicable_chunks),
            chunk_references=chunk_references,
            search_queries=[f"anskaffelse {procurement.category.value} verdi {procurement.value}"],
            processing_time_ms=processing_time_ms
        )
        
        required_requirements = [
            RequirementWithMetadata(
                code=code,
                name=f"Standardkrav {code}",
                description=f"Dette er et seriøsitetskrav for Oslomodellen, kode {code}.",
                mandatory=True,
                source="oslomodellen",
                category="seriøsitet",
                source_chunk_id=next((c['chunk_id'] for c in applicable_chunks if code in c['requirement_codes']), None),
                confidence_score=0.98,
                conditions_met=[f"Verdi ({procurement.value}) er innenfor relevant område for denne regelen."],
            ) for code in sorted(list(all_requirement_codes))
        ]

        assessment = EnhancedOslomodellAssessmentResult(
            procurement_id=procurement.id,
            procurement_name=procurement.name,
            required_requirements=required_requirements,
            crime_risk_assessment=risk,
            social_dumping_risk=risk, # Simplified logic for mock
            subcontractor_assessment={
                "levels_allowed": sub_levels,
                "rationale": f"Risiko vurdert som '{risk}', som tilsier maks {sub_levels} underleverandørledd.",
                "restrictions": ["Alle underleverandører skal forhåndsgodkjennes."] if risk in ["høy", "moderat"] else []
            },
            apprenticeship_assessment={
                "required": procurement.value > 750000 and procurement.duration_months > 3,
                "reason": "Kontraktsverdi og varighet overstiger terskel for lærlingekrav." if procurement.value > 750000 else "Under terskelverdi.",
            },
            assessment_metadata=assessment_metadata,
            overall_confidence=0.95,
            confidence_breakdown={
                "requirement_identification": 0.98,
                "risk_assessment": 0.92,
                "metadata_quality": 0.95
            },
            reasoning_trace=reasoning_trace,
            applied_rules=[{"rule_title": c['title'], "chunk_id": c['chunk_id']} for c in applicable_chunks],
            assessment_date=datetime.now().isoformat(),
            assessed_by="enhanced_oslomodel_agent_v2"
        )
        return assessment

    def _get_all_requirement_codes(self, chunks: List[Dict[str, Any]]) -> set:
        all_codes = set()
        for chunk in chunks:
            codes = chunk.get('requirement_codes', [])
            all_codes.update(codes)
        return all_codes

    async def _multi_strategy_retrieval(self, procurement: ProcurementRequest) -> List[Dict[str, Any]]:
        """
        Mock implementation of retrieval. Returns chunks that resemble the
        'CompleteChunkMetadata' model from chunk_agent.py.
        """
        print("MOCK: Retrieving chunks from vector database...")
        
        # This data simulates the rich metadata you've created in chunk_agent.py
        all_chunks = [
            {
                "chunk_id": "uuid-oslo-regel-1", "title": "Generelle krav for alle anskaffelser",
                "chunk_level": "seksjon", "section_number": "3.1",
                "conditions": [{"description": "Verdi er over 0", "field": "contractValue", "operator": ">=", "value": 0}],
                "requirement_codes": ["A", "B"]
            },
            {
                "chunk_id": "uuid-oslo-regel-2", "title": "Krav for anskaffelser 100k-500k",
                "chunk_level": "underseksjon", "section_number": "4.1.1",
                "conditions": [
                    {"description": "Gjelder for bygg, anlegg og tjenester", "field": "procurementCategory", "operator": "in", "value": ["bygge- og anlegg", "tjeneste", "renhold"]},
                    {"description": "Verdi er mellom 100k og 500k", "field": "contractValue", "operator": "between", "value": [100000, 499999]}
                ],
                "requirement_codes": ["C", "D", "E"]
            },
            {
                "chunk_id": "uuid-oslo-regel-3", "title": "Krav for kontrakter 500k-1.3M",
                "chunk_level": "underseksjon", "section_number": "4.1.2",
                "conditions": [
                    {"description": "Gjelder for bygg, anlegg og tjenester", "field": "procurementCategory", "operator": "in", "value": ["bygge- og anlegg", "tjeneste", "renhold"]},
                    {"description": "Verdi er mellom 500k og 1.3M", "field": "contractValue", "operator": "between", "value": [500000, 1300000]}
                ],
                "requirement_codes": ["F", "G", "H", "I"]
            },
             {
                "chunk_id": "uuid-oslo-regel-4", "title": "Krav for store byggekontrakter over 1.3M",
                "chunk_level": "regel", "section_number": "4.2",
                "conditions": [
                    {"description": "Gjelder kun for Bygg og Anlegg", "field": "procurementCategory", "operator": "in", "value": ["bygge- og anlegg"]},
                    {"description": "Verdi er over 1.3M NOK", "field": "contractValue", "operator": ">=", "value": 1300000}
                ],
                "requirement_codes": ["J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V"]
            },
            {
                "chunk_id": "uuid-oslo-regel-5", "title": "Spesialkrav for IKT-tjenester",
                "chunk_level": "regel", "section_number": "5.1",
                "conditions": [
                    {"description": "Gjelder for IKT-tjenester", "field": "procurementCategory", "operator": "in", "value": ["ikt"]},
                    {"description": "Verdi er over 250k", "field": "contractValue", "operator": ">=", "value": 250000}
                ],
                "requirement_codes": ["IKT-1", "IKT-2"]
            }
        ]
        return all_chunks


async def main():
    # --- Definer Test-scenarioer ---
    test_procurement_1 = {
        "id": "proc-1", "name": "Nytt ventilasjonsanlegg Rådhuset",
        "value": 1_500_000, "category": ProcurementCategory.BYGGE_OG_ANLEGG,
        "duration_months": 8, "description": "Installering av komplett nytt ventilasjonsanlegg i Rådhusets vestfløy.",
        "involves_construction": True
    }
    
    test_procurement_2 = {
        "id": "proc-2", "name": "Rammeavtale renholdstjenester",
        "value": 450_000, "category": ProcurementCategory.RENHOLD,
        "duration_months": 24, "description": "Løpende renhold av kommunale bygg i sentrum.",
    }
    
    agent = EnhancedOslomodelAgent()
    
    print("\n" + "="*50)
    print("--- SCENARIO 1: STOR BYGGEKONTRAKT ---")
    print("="*50)
    result_1 = await agent.execute({"procurement": test_procurement_1})
    print("\n--- AGENT ASSESSMENT RESULT 1 (DETAILED) ---")
    print(json.dumps(result_1, indent=2, ensure_ascii=False))
    
    print("\n" + "="*50)
    print("--- SCENARIO 2: MIDDELS TJENESTEKONTRAKT ---")
    print("="*50)
    result_2 = await agent.execute({"procurement": test_procurement_2})
    print("\n--- AGENT ASSESSMENT RESULT 2 (DETAILED) ---")
    print(json.dumps(result_2, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())