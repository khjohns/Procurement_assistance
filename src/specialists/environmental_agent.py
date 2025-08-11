# src/specialists/environmental_agent.py
"""
Environmental compliance agent with hybrid RAG.
Uses SDK base classes and RPC Gateway for knowledge retrieval.
Assesses procurement against Oslo's climate and environmental requirements.
"""
import os
import json
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.agent_library.core import BaseSpecialistAgent
from src.agent_library.registry import register_tool
from src.agent_library.decorators import build_metadata, with_schemas
from src.models.procurement_models import (
    ProcurementRequest, 
    EnvironmentalAssessmentResult,
    TransportRequirement,
    TransportType,
    EnvironmentalRiskLevel,
    RequirementException
)
from src.tools.rpc_gateway_client import RPCGatewayClient

logger = structlog.get_logger()

ENVIRONMENTAL_METADATA = build_metadata(
    description="Vurderer anskaffelse mot Oslo kommunes klima- og miljøkrav",
    input_schema_class=ProcurementRequest,
    output_schema_class=EnvironmentalAssessmentResult
)

ENVIRONMENTAL_SYSTEM_PROMPT = """
Du er ekspert på Oslo kommunes instruks om bruk av klima- og miljøkrav i bygge- og anleggsanskaffelser.
Din oppgave er å vurdere anskaffelser mot gjeldende krav i instruksen.

VIKTIG Å VURDERE:
- Om standard klima- og miljøkrav skal brukes (alle over 100 000 kr)
- Om utslippsfri massetransport skal premieres (frem til 1.1.2030)
- Om utslippsfrie/biogassbaserte kjøretøy >3.5t skal premieres (frem til 1.1.2027)
- Om unntak kan vurderes pga markedssituasjon eller praktiske hensyn
- Krav til dokumentasjon og oppfølging
- Behov for markedsdialog og tidlig planlegging

Husk viktige frister:
- 1.1.2027: Krav om utslippsfrie/biogassbaserte kjøretøy >3.5t
- 1.1.2030: Slutt på premiering av utslippsfri massetransport

Svar alltid strukturert basert på instruksen.
"""

@register_tool(
    name="agent.run_environmental",
    service_type="specialist_agent",
    metadata=ENVIRONMENTAL_METADATA,
    dependencies=["llm_gateway", "embedding_gateway"]
)
@with_schemas(
    input_schema=ProcurementRequest,
    output_schema=EnvironmentalAssessmentResult
)
class EnvironmentalAgent(BaseSpecialistAgent):
    """
    N3 Specialist: Climate and environmental requirements assessment with hybrid RAG.
    Uses RPC Gateway for all database operations.
    """
    
    def __init__(self, llm_gateway, embedding_gateway):
        super().__init__(llm_gateway)
        self.embedding_gateway = embedding_gateway
        self.rpc_gateway_url = os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
        
        # Valid themes from knowledge base
        self.valid_themes = [
            "Standard klima- og miljøkrav",
            "Utslippsfri massetransport", 
            "Kjøretøy over 3,5 tonn",
            "Unntak",
            "Oppfølging og sanksjonering",
            "Planlegging og markedsdialog"
        ]
        
        # Important dates
        self.key_dates = {
            "heavy_vehicles": datetime(2027, 1, 1),
            "mass_transport_incentives": datetime(2030, 1, 1)
        }
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute environmental assessment with explicit validation at entry and exit.
        """
        # 1. Validate input immediately to a Pydantic object
        try:
            procurement = ProcurementRequest.model_validate(params.get("procurement", params))
        except Exception as e:
            logger.error("Failed to validate procurement input", error=str(e))
            raise ValueError(f"Invalid procurement data: {e}")
        
        logger.info("Starting environmental assessment",
                   procurement_id=procurement.id,
                   name=procurement.name,
                   value=procurement.value,
                   category=procurement.category.value)
        
        # 2. Execute RAG workflow (pass Pydantic object)
        retrieval_plan = await self._plan_retrieval(procurement)
        context_documents = await self._fetch_relevant_context(retrieval_plan, procurement)
        assessment_dict = await self._generate_assessment(procurement, context_documents)
        
        # 3. Validate final result before return
        try:
            final_assessment = EnvironmentalAssessmentResult.model_validate(assessment_dict)
        except Exception as e:
            logger.error("Failed to validate assessment output", error=str(e))
            # Return a safe default assessment rather than failing
            return self._create_default_assessment(procurement).model_dump()
        
        logger.info("Environmental assessment completed",
                   environmental_risk=final_assessment.environmental_risk.value,
                   market_dialogue_recommended=final_assessment.market_dialogue_recommended,
                   transport_requirements_count=len(final_assessment.transport_requirements))
        
        # 4. Return clean dict from validated object
        return final_assessment.model_dump()
    
    async def _plan_retrieval(self, procurement: ProcurementRequest) -> Dict[str, Any]:
        """
        Phase 1: Create retrieval plan based on procurement.
        Now receives a type-safe ProcurementRequest object.
        """
        # Check if it's construction/facility related
        is_construction = procurement.category.value in ['bygge', 'anlegg', 'renhold']
        value = procurement.value
        
        prompt = f"""
        Analyser denne anskaffelsen og planlegg hvilke temaer fra miljøkrav-instruksen som er relevante:

        Anskaffelse:
        - Navn: {procurement.name}
        - Verdi: {value} NOK
        - Kategori: {procurement.category.value}
        - Varighet: {procurement.duration_months} måneder
        - Er bygge/anlegg: {is_construction}
        - Inkluderer bygg: {procurement.includes_construction}
        
        Gyldige temaer: {self.valid_themes}
        
        Spesielt viktig:
        - Er verdien over 100 000 kr?
        - Involverer massetransport?
        - Involverer kjøretøy over 3.5 tonn?
        - Bør unntak vurderes?
        
        Svar KUN med JSON:
        {{
            "themes": ["tema1", "tema2"],
            "value_above_threshold": true/false,
            "involves_mass_transport": true/false,
            "involves_heavy_vehicles": true/false,
            "exception_likely": true/false
        }}
        """
        
        result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "themes": {"type": "array", "items": {"type": "string"}},
                    "value_above_threshold": {"type": "boolean"},
                    "involves_mass_transport": {"type": "boolean"},
                    "involves_heavy_vehicles": {"type": "boolean"},
                    "exception_likely": {"type": "boolean"}
                },
                "required": ["themes", "value_above_threshold", "involves_mass_transport", 
                           "involves_heavy_vehicles", "exception_likely"]
            },
            purpose="fast_evaluation",
            temperature=0.3
        )
        
        return result
    
    async def _fetch_relevant_context(self, 
                                    plan: Dict[str, Any], 
                                    procurement: ProcurementRequest) -> List[Dict[str, Any]]:
        """
        Phase 2: Fetch relevant context from knowledge base via RPC.
        Now receives a type-safe ProcurementRequest object.
        """
        context_documents = []
        
        async with RPCGatewayClient(
            agent_id="environmental_agent",
            gateway_url=self.rpc_gateway_url
        ) as rpc_client:
            
            # Always fetch basic requirements if value > 100k
            if plan.get("value_above_threshold"):
                if "Standard klima- og miljøkrav" not in plan.get("themes", []):
                    plan["themes"].append("Standard klima- og miljøkrav")
            
            for theme in plan.get("themes", []):
                logger.debug("Fetching context for theme", theme=theme)
                
                # Build search query using Pydantic object fields
                search_query = f"{theme} {procurement.category.value} {procurement.value} NOK"
                
                # Generate embedding
                query_embedding = await self.embedding_gateway.create_embedding(
                    text=search_query,
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=1536
                )
                
                # Search via RPC
                search_result = await rpc_client.call("database.search_miljokrav_documents", {
                    "queryEmbedding": query_embedding,
                    "threshold": 0.6,
                    "limit": 8,
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
        return context_documents[:8]
    
    async def _generate_assessment(self, 
                                  procurement: ProcurementRequest, 
                                  context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 3: Generate assessment based on procurement and context.
        Now receives a type-safe ProcurementRequest object.
        """
        # Format context for prompt
        context_text = "\n\n".join([
            f"[{doc.get('documentId', 'unknown')}] (Relevans: {doc.get('relevance_score', 0):.2f})\n{doc.get('content', '')}"
            for doc in context
        ])
        
        # Check dates
        current_date = datetime.now()
        is_before_2027 = current_date < self.key_dates["heavy_vehicles"]
        is_before_2030 = current_date < self.key_dates["mass_transport_incentives"]
        
        prompt = f"""
        {ENVIRONMENTAL_SYSTEM_PROMPT}
        
        RELEVANT INSTRUKS-KONTEKST:
        {context_text if context_text else "Ingen spesifikk kontekst funnet, bruk generell kunnskap om miljøkrav-instruksen."}
        
        ANSKAFFELSE TIL VURDERING:
        - ID: {procurement.id}
        - Navn: {procurement.name}
        - Verdi: {procurement.value} NOK
        - Kategori: {procurement.category.value}
        - Beskrivelse: {procurement.description}
        - Varighet: {procurement.duration_months} måneder
        - Inkluderer bygge/anlegg: {procurement.includes_construction}
        
        DAGENS DATO: {current_date.strftime('%Y-%m-%d')}
        - Før 1.1.2027 (kjøretøy >3.5t): {is_before_2027}
        - Før 1.1.2030 (massetransport): {is_before_2030}
        
        VIKTIG: Svar med et komplett JSON-objekt som nøyaktig følger `EnvironmentalAssessmentResult`-schemaet.
        Vær spesielt nøye med å fylle ut `environmental_risk` og den strukturerte `transport_requirements`-listen basert på din analyse.
        }}
        """
        
        result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema=EnvironmentalAssessmentResult.model_json_schema(),
            purpose="complex_reasoning",
            temperature=0.3
        )
        
        # Add metadata using Pydantic object fields
        result['procurement_id'] = procurement.id
        result['procurement_name'] = procurement.name
        result['assessment_date'] = datetime.now().isoformat()
        result['context_documents_used'] = [doc.get('documentId', 'unknown') for doc in context]
        
        # Ensure required fields have sensible defaults
        if not result.get('documentation_requirements'):
            result['documentation_requirements'] = [
                "Dokumenter vurderinger i kontraktsstrategien",
                "Begrunne valg i anskaffelsesdokumentene"
            ]
        
        if not result.get('important_deadlines'):
            result['important_deadlines'] = {}
            if is_before_2027:
                result['important_deadlines']['kjøretøy_35tonn'] = "2027-01-01"
            if is_before_2030:
                result['important_deadlines']['massetransport'] = "2030-01-01"
        
        # Set default environmental risk if not provided
        if not result.get('environmental_risk'):
            if procurement.value > 50_000_000:  # Over 50M NOK
                result['environmental_risk'] = 'høy'
            elif procurement.value > 5_000_000:  # Over 5M NOK
                result['environmental_risk'] = 'middels'
            else:
                result['environmental_risk'] = 'lav'
        
        return result
    
    def _create_default_assessment(self, procurement: ProcurementRequest) -> EnvironmentalAssessmentResult:
        """
        Create a safe default assessment when generation or validation fails.
        """
        current_date = datetime.now()
        is_before_2027 = current_date < self.key_dates["heavy_vehicles"]
        is_before_2030 = current_date < self.key_dates["mass_transport_incentives"]
        
        # Determine risk level based on value
        if procurement.value > 50_000_000:
            risk_level = EnvironmentalRiskLevel.HIGH
        elif procurement.value > 5_000_000:
            risk_level = EnvironmentalRiskLevel.MEDIUM
        else:
            risk_level = EnvironmentalRiskLevel.LOW
        
        # Create deadlines dict
        deadlines = {}
        if is_before_2027:
            deadlines['kjøretøy_35tonn'] = "2027-01-01"
        if is_before_2030:
            deadlines['massetransport'] = "2030-01-01"
        
        return EnvironmentalAssessmentResult(
            procurement_id=procurement.id,
            procurement_name=procurement.name,
            assessed_by="environmental_agent",
            environmental_risk=risk_level,
            climate_impact_assessed=True,
            transport_requirements=[],
            exceptions_recommended=[],
            minimum_biofuel_required=False,
            important_deadlines=deadlines,
            documentation_requirements=[
                "Dokumenter vurderinger i kontraktsstrategien",
                "Begrunne valg i anskaffelsesdokumentene"
            ],
            follow_up_points=[
                "Vurder markedssituasjon før kravstilling",
                "Planlegg oppfølging av miljøkrav i kontraktsperioden"
            ],
            market_dialogue_recommended=procurement.value > 10_000_000,
            award_criteria_recommended=[],
            recommendations=[
                "Følg standard klima- og miljøkrav for anskaffelsen",
                "Vurder behov for tidlig markedsdialog"
            ],
            confidence=0.5  # Low confidence for default assessment
        )