# src/specialists/oslomodell_agent.py
"""
Oslomodell compliance agent with hybrid RAG.
Uses SDK base classes and RPC Gateway for knowledge retrieval.
"""
import os
import json
import structlog
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from src.agent_library.core import BaseSpecialistAgent
from src.agent_library.registry import register_tool
from src.agent_library.decorators import build_metadata, with_schemas
from src.models.procurement_models import ProcurementRequest
from src.tools.rpc_gateway_client import RPCGatewayClient

logger = structlog.get_logger()

# Pydantic models for Oslomodell
class OslomodellAssessment(BaseModel):
    """Result from Oslomodell assessment."""
    vurdert_risiko_for_akrim: str = Field(..., description="Vurdert risiko: høy/moderat/lav")
    påkrevde_seriøsitetskrav: List[str] = Field(..., description="Liste over påkrevde krav")
    anbefalt_antall_underleverandørledd: int = Field(..., description="Maks antall underleverandørledd")
    aktsomhetsvurdering_kravsett: Optional[str] = Field(None, description="Kravsett A eller B")
    krav_om_lærlinger: Dict[str, Any] = Field(..., description="Info om lærlingkrav")
    recommendations: List[str] = Field(default_factory=list, description="Anbefalinger")
    confidence: float = Field(..., ge=0.0, le=1.0)

OSLOMODELL_METADATA = build_metadata(
    description="Vurderer anskaffelse mot Oslomodellens krav med hybrid RAG",
    input_schema_class=ProcurementRequest,
    output_schema_class=OslomodellAssessment
)

OSLOMODELL_SYSTEM_PROMPT = """
Du er ekspert på Oslomodellen og Oslo kommunes anskaffelsesinstruks.
Din oppgave er å vurdere anskaffelser mot gjeldende krav.

VIKTIG:
- Vurder risiko for arbeidslivskriminalitet og sosial dumping
- Identifiser påkrevde seriøsitetskrav basert på type og verdi
- Anbefall antall underleverandørledd basert på risiko
- Sjekk krav om lærlinger hvis over 1.3M og varighet > 3 mnd

Svar alltid strukturert basert på instruksen.
"""

@register_tool(
    name="agent.run_oslomodell",
    service_type="specialist_agent",
    metadata=OSLOMODELL_METADATA,
    dependencies=["llm_gateway", "embedding_gateway"]
)
@with_schemas(
    input_schema=ProcurementRequest,
    output_schema=OslomodellAssessment
)
class OslomodellAgent(BaseSpecialistAgent):
    """
    N3 Specialist: Oslo Model compliance assessment with hybrid RAG.
    Uses RPC Gateway for all database operations.
    """
    
    def __init__(self, llm_gateway, embedding_gateway):
        super().__init__(llm_gateway)
        self.embedding_gateway = embedding_gateway
        self.rpc_gateway_url = os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
        
        # Temaer fra kunnskapsbase
        self.valid_themes = ["Seriøsitetskrav", "Aktsomhetsvurderinger", "Lærlinger"]
        
        # Fagområder med særlig behov for lærlinger
        self.lærling_fagområder = [
            "tømrerfaget", "rørleggerfaget", "elektrofag", "betongfaget",
            "malerfaget", "murerfaget", "anleggsfaget", "ventilasjonfaget"
        ]
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Oslomodell assessment with 3-phase hybrid RAG.
        """
        procurement_data = params.get("procurement", params)
        
        logger.info("Starting Oslomodell assessment", 
                   name=procurement_data.get('name'),
                   value=procurement_data.get('value'))
        
        # Phase 1: Plan retrieval
        retrieval_plan = await self._plan_retrieval(procurement_data)
        
        # Phase 2: Fetch relevant context
        context_documents = await self._fetch_relevant_context(retrieval_plan, procurement_data)
        
        # Phase 3: Generate assessment
        assessment = await self._generate_assessment(procurement_data, context_documents)
        
        logger.info("Oslomodell assessment completed",
                   risk=assessment.get('vurdert_risiko_for_akrim'),
                   requirements_count=len(assessment.get('påkrevde_seriøsitetskrav', [])))
        
        return assessment
    
    async def _plan_retrieval(self, procurement: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 1: Create retrieval plan based on procurement.
        """
        prompt = f"""
        Analyser denne anskaffelsen og planlegg hvilke temaer fra Oslomodellen som er relevante:

        Anskaffelse:
        - Navn: {procurement.get('name')}
        - Verdi: {procurement.get('value')} NOK
        - Kategori: {procurement.get('category', 'ukjent')}
        - Varighet: {procurement.get('duration_months', 0)} måneder
        
        Gyldige temaer: {self.valid_themes}
        
        Svar KUN med JSON:
        {{
            "themes": ["tema1", "tema2"],
            "risk_indicators": ["indikator1", "indikator2"],
            "requires_apprentices": true/false
        }}
        """
        
        result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "themes": {"type": "array", "items": {"type": "string"}},
                    "risk_indicators": {"type": "array", "items": {"type": "string"}},
                    "requires_apprentices": {"type": "boolean"}
                }
            },
            purpose="fast_evaluation",
            temperature=0.3
        )
        
        return result
    
    async def _fetch_relevant_context(self, 
                                    plan: Dict[str, Any], 
                                    procurement: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Phase 2: Fetch relevant context from knowledge base via RPC.
        """
        context_documents = []
        
        async with RPCGatewayClient(
            agent_id="oslomodell_agent",
            gateway_url=self.rpc_gateway_url
        ) as rpc_client:
            
            for theme in plan.get("themes", []):
                logger.debug("Fetching context for theme", theme=theme)
                
                # Build search query
                search_query = f"{theme} {procurement.get('name', '')} {procurement.get('value', 0)} NOK"
                
                # Generate embedding
                query_embedding = await self.embedding_gateway.create_embedding(
                    text=search_query,
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=1536
                )
                
                # Search via RPC
                search_result = await rpc_client.call("database.search_knowledge_documents", {
                    "queryEmbedding": query_embedding,
                    "threshold": 0.6,  # Slightly lower threshold for better recall
                    "limit": 3,
                    "metadataFilter": {"tema": theme} if theme in self.valid_themes else {}
                })
                
                if search_result.get('status') == 'success':
                    docs = search_result.get('results', [])
                    
                    for doc in docs:
                        doc["theme"] = theme
                        doc["relevance_score"] = doc.get("similarity", 0.0)
                        
                        if doc["relevance_score"] > 0.6:
                            context_documents.append(doc)
                            logger.debug(f"Added relevant doc: {doc.get('documentId')}")
                else:
                    logger.warning(f"Search failed for theme: {theme}", 
                                 error=search_result.get('message'))
        
        # Sort by relevance
        context_documents.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Limit to top 5 most relevant
        return context_documents[:5]
    
    async def _generate_assessment(self, 
                                  procurement: Dict[str, Any], 
                                  context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 3: Generate assessment based on procurement and context.
        """
        # Format context for prompt
        context_text = "\n\n".join([
            f"[{doc.get('documentId', 'unknown')}] (Relevans: {doc.get('relevance_score', 0):.2f})\n{doc.get('content', '')}"
            for doc in context
        ])
        
        prompt = f"""
        {OSLOMODELL_SYSTEM_PROMPT}
        
        RELEVANT INSTRUKS-KONTEKST:
        {context_text if context_text else "Ingen spesifikk kontekst funnet, bruk generell kunnskap om Oslomodellen."}
        
        ANSKAFFELSE TIL VURDERING:
        - Navn: {procurement.get('name')}
        - Verdi: {procurement.get('value')} NOK
        - Kategori: {procurement.get('category', 'ukjent')}
        - Beskrivelse: {procurement.get('description', 'Ingen beskrivelse')}
        - Varighet: {procurement.get('duration_months', 0)} måneder
        
        Vurder og svar med strukturert JSON:
        {{
            "vurdert_risiko_for_akrim": "høy/moderat/lav",
            "påkrevde_seriøsitetskrav": ["krav1", "krav2", ...],
            "anbefalt_antall_underleverandørledd": 0-2,
            "aktsomhetsvurdering_kravsett": "A/B/Ikke påkrevd",
            "krav_om_lærlinger": {{
                "status": true/false,
                "begrunnelse": "...",
                "antall_lærlinger": 0
            }},
            "recommendations": ["anbefaling1", "anbefaling2", ...],
            "confidence": 0.0-1.0
        }}
        """
        
        result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema=OslomodellAssessment.model_json_schema(),
            purpose="complex_reasoning",
            temperature=0.3
        )
        
        # Ensure all required fields
        if not result.get('påkrevde_seriøsitetskrav'):
            result['påkrevde_seriøsitetskrav'] = self._get_default_requirements(
                procurement.get('value', 0),
                procurement.get('category', 'tjeneste')
            )
        
        return result
    
    def _get_default_requirements(self, value: int, category: str) -> List[str]:
        """
        Get default requirements based on value and category.
        Fallback when LLM doesn't provide requirements.
        """
        requirements = []
        
        if category in ["bygge", "anlegg", "renhold"]:
            if value < 500_000:
                requirements = ["A", "B", "C", "D", "E"]
            else:
                requirements = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", 
                              "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"]
        else:  # tjeneste or other
            if value < 500_000:
                requirements = ["A", "B", "C", "D", "E"]
            else:
                requirements = ["A", "B", "C", "D", "E", "F", "G", "H"]
        
        return requirements
