# src/specialists/oslomodell_agent.py - SIMPLIFIED REFACTORED VERSION
"""
Oslomodell compliance agent - Simplified to only identify requirement codes.
The actual requirement details come from separate contract documents.
"""
import os
import json
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.agent_library.core import BaseSpecialistAgent
from src.agent_library.registry import register_tool
from src.agent_library.decorators import build_metadata, with_schemas

# Import centralized models
from src.models.procurement_models_refactored import (
    ProcurementRequest,
    OslomodellAssessmentResult,
    Requirement,
    RequirementSource,
    RequirementCategory,
    ApprenticeshipRequirement
)
from src.tools.rpc_gateway_client import RPCGatewayClient

logger = structlog.get_logger()

OSLOMODELL_METADATA = build_metadata(
    description="Identifiserer relevante Oslomodell-kravkoder basert på instruks",
    input_schema_class=ProcurementRequest,
    output_schema_class=OslomodellAssessmentResult
)

OSLOMODELL_SYSTEM_PROMPT = """
Du er ekspert på Oslo kommunes instruks for anskaffelser og Oslomodellen.
Din oppgave er å identifisere hvilke KRAVKODER (A-V) som gjelder for en anskaffelse.

VIKTIGE REGLER FRA INSTRUKSEN:

1. SERIØSITETSKRAV (punkt 4):
   - 100k-500k bygge/anlegg/tjeneste: Alltid A-E. Ved risiko også F-T.
   - Over 500k bygge/anlegg/renhold: Alltid A-U
   - Over 500k tjeneste: Alltid A-H. Ved risiko også I-T.

2. LÆRLINGKRAV (punkt 6):
   - Krav V: Ved anskaffelser over statlig terskelverdi (1.3M), varighet >3 mnd, utførende fag

3. UNDERLEVERANDØRER (punkt 5):
   - Høy risiko: 0 ledd (kan nektes)
   - Moderat risiko: 1 ledd
   - Lav risiko: 2 ledd

4. AKTSOMHETSVURDERING (punkt 7):
   - Over 500k med høy risiko: Kravsett A eller B

OPPGAVE:
- Identifiser BARE relevante kravkoder (A, B, C, osv.)
- IKKE generer beskrivelser av kravene
- Vurder risiko for arbeidslivskriminalitet
- Avgjør antall underleverandørledd
- Vurder om lærlinger kreves
"""

@register_tool(
    name="agent.run_oslomodell",
    service_type="specialist_agent",
    metadata=OSLOMODELL_METADATA,
    dependencies=["llm_gateway", "embedding_gateway"]
)
@with_schemas(
    input_schema=ProcurementRequest,
    output_schema=OslomodellAssessmentResult
)
class OslomodellAgent(BaseSpecialistAgent):
    """
    Simplified N3 Specialist: Identifies Oslomodell requirement codes.
    Does NOT generate requirement descriptions - these come from contract documents.
    """
    
    def __init__(self, llm_gateway, embedding_gateway):
        super().__init__(llm_gateway)
        self.embedding_gateway = embedding_gateway
        self.rpc_gateway_url = os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
        
        # Themes for knowledge retrieval
        self.valid_themes = ["Seriøsitetskrav", "Lærlinger", "Aktsomhetsvurderinger"]
        
        # Trade fields requiring apprentices
        self.apprentice_trades = [
            "tømrerfaget", "rørleggerfaget", "elektrofag", "betongfaget",
            "malerfaget", "murerfaget", "anleggsfaget", "ventilasjonfaget"
        ]
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Oslomodell assessment - identifies requirement codes only.
        """
        # Validate input
        procurement = ProcurementRequest.model_validate(params.get("procurement", params))
        
        logger.info("Starting Oslomodell assessment", 
                   procurement_id=procurement.id,
                   name=procurement.name,
                   value=procurement.value,
                   category=procurement.category.value)
        
        # Phase 1: Plan retrieval
        retrieval_plan = await self._plan_retrieval(procurement)
        
        # Phase 2: Fetch relevant context from instruks
        context_documents = await self._fetch_relevant_context(retrieval_plan, procurement)
        
        # Phase 3: Generate assessment (requirement codes only)
        assessment_dict = await self._generate_assessment(procurement, context_documents)
        
        # Validate output
        assessment = OslomodellAssessmentResult.model_validate(assessment_dict)
        
        logger.info("Oslomodell assessment completed",
                   procurement_id=assessment.procurement_id,
                   risk=assessment.crime_risk_assessment,
                   requirement_codes=[req.code for req in assessment.required_requirements],
                   apprentices_required=assessment.apprenticeship_requirement.required)
        
        return assessment.model_dump()
    
    async def _plan_retrieval(self, procurement: ProcurementRequest) -> Dict[str, Any]:
        """
        Phase 1: Plan what to retrieve from instruks.
        """
        # Determine key factors
        value_range = "under_100k" if procurement.value < 100_000 else \
                     "100k_500k" if procurement.value < 500_000 else "over_500k"
        
        is_construction = procurement.category.value in ["bygge", "anlegg", "renhold"]
        is_service = procurement.category.value in ["tjeneste", "konsulent", "it"]
        
        prompt = f"""
        Analyser denne anskaffelsen mot Oslomodell-instruksen:
        
        Anskaffelse:
        - Navn: {procurement.name}
        - Verdi: {procurement.value} NOK ({value_range})
        - Kategori: {procurement.category.value} 
        - Varighet: {procurement.duration_months} måneder
        - Er bygge/anlegg/renhold: {is_construction}
        - Er tjeneste: {is_service}
        
        Vurder:
        1. Risiko for arbeidslivskriminalitet (høy/moderat/lav)
        2. Om lærlinger kreves (verdi >1.3M, varighet >3mnd, utførende fag)
        3. Hvilke instrukspunkter som er relevante
        
        Svar med JSON:
        {{
            "themes": ["Seriøsitetskrav"],
            "risk_level": "høy/moderat/lav",
            "requires_apprentices": true/false,
            "relevant_sections": ["4.1", "4.2", "5.1", "6", "7.3"]
        }}
        """
        
        result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "themes": {"type": "array", "items": {"type": "string"}},
                    "risk_level": {"type": "string", "enum": ["høy", "moderat", "lav"]},
                    "requires_apprentices": {"type": "boolean"},
                    "relevant_sections": {"type": "array", "items": {"type": "string"}}
                }
            },
            purpose="fast_evaluation",
            temperature=0.2
        )
        
        return result
    
    async def _fetch_relevant_context(self, 
                                    plan: Dict[str, Any], 
                                    procurement: ProcurementRequest) -> List[Dict[str, Any]]:
        """
        Phase 2: Fetch relevant sections from instruks knowledge base.
        """
        context_documents = []
        
        async with RPCGatewayClient(
            agent_id="oslomodell_agent",
            gateway_url=self.rpc_gateway_url
        ) as rpc_client:
            
            # Build search queries for relevant sections
            relevant_sections = plan.get("relevant_sections", ["4", "5", "6", "7"])
            
            for section in relevant_sections:
                search_query = f"punkt {section} {procurement.category.value} {procurement.value}"
                
                # Generate embedding
                query_embedding = await self.embedding_gateway.create_embedding(
                    text=search_query,
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=1536
                )
                
                # Search knowledge base
                search_result = await rpc_client.call("database.search_knowledge_documents", {
                    "queryEmbedding": query_embedding,
                    "threshold": 0.7,
                    "limit": 2,
                    "metadataFilter": {}
                })
                
                if search_result.get('status') == 'success':
                    docs = search_result.get('results', [])
                    for doc in docs:
                        if doc.get("similarity", 0) > 0.7:
                            context_documents.append(doc)
        
        # Deduplicate and sort by relevance
        seen = set()
        unique_docs = []
        for doc in context_documents:
            doc_id = doc.get('documentId')
            if doc_id not in seen:
                seen.add(doc_id)
                unique_docs.append(doc)
        
        unique_docs.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return unique_docs[:5]
    
    async def _generate_assessment(self, 
                                  procurement: ProcurementRequest,
                                  context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 3: Generate assessment identifying requirement CODES only.
        """
        # Format context
        context_text = "\n\n".join([
            f"[Instruks {doc.get('documentId', '')}]\n{doc.get('content', '')}"
            for doc in context
        ])
        
        # Determine value category for clearer instructions
        if procurement.value < 100_000:
            value_category = "UNDER 100k - Oslomodellen gjelder ikke"
            base_requirements = []
        elif procurement.value < 500_000:
            value_category = "100k-500k"
            if procurement.category.value in ["bygge", "anlegg"]:
                base_requirements = ["A", "B", "C", "D", "E"]  # Alltid A-E
            else:
                base_requirements = ["A", "B", "C", "D", "E"]  # Tjeneste også A-E
        else:  # Over 500k
            value_category = "OVER 500k"
            if procurement.category.value in ["bygge", "anlegg", "renhold"]:
                base_requirements = list("ABCDEFGHIJKLMNOPQRSTU")  # A-U alltid
            else:  # Tjeneste
                base_requirements = list("ABCDEFGH")  # A-H alltid
        
        prompt = f"""
        {OSLOMODELL_SYSTEM_PROMPT}
        
        INSTRUKS-KONTEKST:
        {context_text if context_text else "Bruk generell kunnskap om Oslomodell-instruksen."}
        
        ANSKAFFELSE:
        - Navn: {procurement.name}
        - Verdi: {procurement.value} NOK ({value_category})
        - Kategori: {procurement.category.value}
        - Varighet: {procurement.duration_months} måneder
        - Bygge/anlegg: {procurement.includes_construction}
        
        BASISKRAV for denne kategorien: {base_requirements}
        
        Generer vurdering som JSON. VIKTIG:
        
        For "required_requirements": List opp BARE kravkoder som Requirement-objekter.
        Eksempel format:
        {{
            "code": "A",
            "name": "Krav A",  # Kun generisk navn
            "description": "Oslomodell krav A",  # IKKE detaljert beskrivelse
            "mandatory": true,
            "source": "oslomodellen",
            "category": "seriøsitet"
        }}
        
        IKKE generer detaljerte beskrivelser - det kommer fra kontraktsdokumenter.
        
        Inkluder også:
        - crime_risk_assessment: "høy"/"moderat"/"lav"
        - dd_risk_assessment: "høy"/"moderat"/"lav"           # NYE! Human rights due diligence
        - social_dumping_risk: "høy"/"moderat"/"lav"
        - subcontractor_levels: 0-2 basert på risiko
        - apprenticeship_requirement: Strukturert objekt
        - due_diligence_requirement: "A"/"B"/"Ikke påkrevd"
        """
        
        result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema=OslomodellAssessmentResult.model_json_schema(),
            purpose="complex_reasoning",
            temperature=0.2
        )
        
        # Add metadata
        result['procurement_id'] = procurement.id
        result['procurement_name'] = procurement.name
        result['assessment_date'] = datetime.now().isoformat()
        result['context_documents_used'] = [doc.get('documentId', 'unknown') for doc in context]
        
        # Ensure requirements are simplified (backup processing)
        if result.get('required_requirements'):
            simplified_requirements = []
            for req in result['required_requirements']:
                if isinstance(req, dict):
                    # Ensure we only have code references, not detailed descriptions
                    simplified_req = {
                        "code": req.get("code", "?"),
                        "name": f"Krav {req.get('code', '?')}",
                        "description": f"Oslomodell seriøsitetskrav {req.get('code', '?')}",
                        "mandatory": req.get("mandatory", True),
                        "source": "oslomodellen",
                        "category": req.get("category", "seriøsitet")
                    }
                    simplified_requirements.append(simplified_req)
                elif isinstance(req, str):
                    # Convert string to simplified requirement
                    simplified_requirements.append({
                        "code": req,
                        "name": f"Krav {req}",
                        "description": f"Oslomodell seriøsitetskrav {req}",
                        "mandatory": True,
                        "source": "oslomodellen",
                        "category": "seriøsitet"
                    })
            result['required_requirements'] = simplified_requirements
        
        # Ensure apprenticeship_requirement is properly structured
        if not isinstance(result.get('apprenticeship_requirement'), dict):
            result['apprenticeship_requirement'] = self._determine_apprentice_requirement(procurement)
        
        return result
    
    def _determine_apprentice_requirement(self, procurement: ProcurementRequest) -> Dict[str, Any]:
        """
        Determine if apprentices are required based on instruks punkt 6.
        """
        # Statlig terskelverdi = 1.3M NOK
        value_threshold = procurement.value > 1_300_000
        duration_threshold = procurement.duration_months > 3
        
        # Check if it's an executing trade
        relevant_category = procurement.category.value in ["bygge", "anlegg"]
        
        required = value_threshold and duration_threshold and relevant_category
        
        return {
            "required": required,
            "reason": f"{'Verdi over 1.3M' if value_threshold else 'Under terskelverdi'}, "
                     f"{'varighet over 3 mnd' if duration_threshold else 'kort varighet'}, "
                     f"{'utførende fag' if relevant_category else 'ikke utførende fag'}",
            "minimum_count": 1 if required else 0,
            "applicable_trades": self.apprentice_trades if relevant_category else [],
            "threshold_exceeded": value_threshold
        }