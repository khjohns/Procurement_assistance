# claude_oslomodel_agent.py
"""
Revised Oslomodel compliance agent that leverages enhanced chunk metadata.
Uses multi-strategy retrieval and constraint-based reasoning.
"""
import os
import json
import structlog
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import asyncio

from src.agent_library.core import BaseSpecialistAgent
from src.agent_library.registry import register_tool
from src.agent_library.decorators import build_metadata, with_schemas

# Import centralized models
from src.tools.rpc_gateway_client import RPCGatewayClient
from src.tools.embedding_gateway import EmbeddingGateway
from src.tools.llm_gateway import LLMGateway
from src.models.procurement_models import (
    ProcurementRequest, 
    OslomodellAssessmentResult,
    ApprenticeshipRequirement,
    Requirement,
    RequirementCategory
)

logger = structlog.get_logger()

OSLOMODELL_METADATA = build_metadata(
    description="Enhanced Oslomodell agent with rich metadata retrieval",
    input_schema_class=ProcurementRequest,
    output_schema_class=OslomodellAssessmentResult
)

OSLOMODELL_SYSTEM_PROMPT = """
Du er ekspert på Oslo kommunes instruks for anskaffelser og Oslomodellen.
Din oppgave er å identifisere hvilke KRAVKODER (A-V) som gjelder basert på strukturert metadata.

VIKTIG: Du får allerede strukturert metadata om regler. Bruk denne direkte.
- Sjekk conditions arrays for når regler gjelder
- Se på key_values_and_thresholds for beløpsgrenser
- Bruk risk_level arrays for risikovurdering
- Les requirement_codes for hvilke krav som gjelder

Returner:
- required_requirements: Liste med kravkoder som gjelder
- crime_risk_assessment: "høy"/"moderat"/"lav" 
- subcontractor_levels: 0-2 basert på risiko
- apprenticeship_requirement: Strukturert objekt om lærlinger
- confidence: Din sikkerhet på vurderingen (0.0-1.0)
"""

@register_tool(
    name="agent.run_oslomodell_enhanced",
    service_type="specialist_agent",
    metadata=OSLOMODELL_METADATA,
    dependencies=["llm_gateway", "embedding_gateway"],
    save_method="database.save_oslomodell_assessment"
)
@with_schemas(
    input_schema=ProcurementRequest,
    output_schema=OslomodellAssessmentResult
)
class EnhancedOslomodelAgent(BaseSpecialistAgent):
    """
    Enhanced Oslomodell agent that leverages rich chunk metadata for precise assessments.
    """
    
    def __init__(self, llm_gateway, embedding_gateway):
        super().__init__(llm_gateway)
        self.embedding_gateway = embedding_gateway
        self.rpc_gateway_url = os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
        
        # Trade fields requiring apprentices
        self.apprentice_trades = [
            "tømrerfaget", "rørleggerfaget", "elektrofag", "betongfaget",
            "malerfaget", "murerfaget", "anleggsfaget", "ventilasjonfaget"
        ]
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute enhanced Oslomodell assessment using rich metadata.
        """
        # Validate input
        procurement = ProcurementRequest.model_validate(params.get("procurement", params))
        
        logger.info("Starting enhanced Oslomodell assessment", 
                   procurement_id=procurement.id,
                   name=procurement.name,
                   value=procurement.value,
                   category=procurement.category.value)
        
        # Phase 1: Multi-strategy retrieval
        relevant_chunks = await self._multi_strategy_retrieval(procurement)
        
        # Phase 2: Build requirement graph from metadata
        requirement_graph = self._build_requirement_graph(relevant_chunks)
        
        # Phase 3: Apply constraint satisfaction
        applicable_requirements = self._apply_constraints(
            requirement_graph, 
            procurement, 
            relevant_chunks
        )
        
        # Phase 4: Generate structured assessment
        assessment_dict = await self._generate_assessment(
            procurement, 
            applicable_requirements, 
            relevant_chunks
        )
        
        # Validate output
        assessment = OslomodellAssessmentResult.model_validate(assessment_dict)
        
        logger.info("Enhanced Oslomodell assessment completed",
                   procurement_id=assessment.procurement_id,
                   risk=assessment.crime_risk_assessment,
                   requirement_codes=[req.code for req in assessment.required_requirements],
                   apprentices_required=assessment.apprenticeship_requirement.required)
        
        return assessment.model_dump()
    
    async def _multi_strategy_retrieval(self, 
                                       procurement: ProcurementRequest) -> List[Dict[str, Any]]:
        """
        Phase 1: Multi-strategy retrieval using different search approaches.
        """
        all_chunks = []
        
        async with RPCGatewayClient(
            agent_id="oslomodel_agent_enhanced",
            gateway_url=self.rpc_gateway_url
        ) as rpc_client:
            
            # Strategy 1: Semantic search with embedding
            if self.embedding_gateway:
                query_text = f"{procurement.category.value} anskaffelse {procurement.value} NOK"
                query_embedding = await self.embedding_gateway.create_embedding(
                    text=query_text,
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=1536
                )
                
                semantic_results = await rpc_client.call("database.search_enhanced_chunks", {
                    "p_query_embedding": query_embedding,
                    "p_limit": 5
                })
                
                if semantic_results.get('status') == 'success':
                    all_chunks.extend(semantic_results.get('results', []))
            
            # Strategy 2: Structured search by value and category
            category_map = {
                "CONSTRUCTION": "bygge- og anlegg",
                "SERVICE": "tjeneste", 
                "GOODS": "vare",
                "CLEANING": "renhold"
            }
            
            structured_results = await rpc_client.call("database.search_enhanced_chunks", {
                "p_categories": [category_map.get(procurement.category.value, "tjeneste")],
                "p_value_min": procurement.value - 1,  # Slightly below to catch boundaries
                "p_value_max": procurement.value + 1000000,  # Include higher tiers
                "p_limit": 10
            })
            
            if structured_results.get('status') == 'success':
                all_chunks.extend(structured_results.get('results', []))
            
            # Strategy 3: Section-based retrieval for key sections
            relevant_sections = ["4.1", "4.2", "4.3", "5.1", "6", "7.1", "7.3", "7.4"]
            
            for section in relevant_sections:
                section_results = await rpc_client.call("database.search_enhanced_chunks", {
                    "p_section_numbers": [section],
                    "p_limit": 2
                })
                
                if section_results.get('status') == 'success':
                    all_chunks.extend(section_results.get('results', []))
            
            # Strategy 4: Risk-based retrieval if high-value procurement
            if procurement.value > 1000000:
                risk_results = await rpc_client.call("database.get_chunks_by_risk_level", {
                    "p_risk_level": "høy",
                    "p_risk_context": "arbeidslivskriminalitet"
                })
                
                if risk_results.get('status') == 'success':
                    all_chunks.extend(risk_results.get('results', []))
        
        # Deduplicate chunks
        seen_ids = set()
        unique_chunks = []
        for chunk in all_chunks:
            chunk_id = chunk.get('chunk_id')
            if chunk_id and chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                unique_chunks.append(chunk)
        
        # Sort by relevance
        unique_chunks.sort(
            key=lambda x: (
                x.get('relevance_score', 0) * 0.5 + 
                x.get('similarity_score', 0) * 0.5
            ),
            reverse=True
        )
        
        return unique_chunks[:10]  # Top 10 most relevant
    
    def _build_requirement_graph(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 2: Build a requirement graph from chunk metadata.
        """
        graph = {
            "mandatory_requirements": set(),
            "conditional_requirements": {},
            "value_based_requirements": {},
            "risk_based_requirements": {},
            "apprentice_requirements": {},
            "subcontractor_rules": []
        }
        
        for chunk in chunks:
            # Extract requirement codes
            req_codes = chunk.get('requirement_codes', [])
            conditions = chunk.get('conditions', [])
            thresholds = chunk.get('key_values_and_thresholds', {})
            risk_levels = chunk.get('risk_level', [])
            
            # Process conditions to determine requirement types
            for condition in conditions:
                if isinstance(condition, dict):
                    desc = condition.get('description', '')
                    field = condition.get('field', '')
                    operator = condition.get('operator', '')
                    value = condition.get('value', '')
                    
                    # Mandatory requirements (always apply)
                    if 'alltid' in desc.lower() or operator == 'always':
                        codes = self._extract_codes_from_description(desc)
                        graph["mandatory_requirements"].update(codes)
                    
                    # Value-based requirements
                    elif field == 'value' and operator == 'between':
                        if isinstance(value, dict):
                            min_val = value.get('min', 0)
                            max_val = value.get('max', float('inf'))
                            codes = self._extract_codes_from_description(desc)
                            graph["value_based_requirements"][f"{min_val}-{max_val}"] = codes
                    
                    # Risk-based requirements
                    elif 'risiko' in desc.lower() or field == 'risk_detected':
                        codes = self._extract_codes_from_description(desc)
                        graph["risk_based_requirements"]["any_risk"] = codes
            
            # Process subcontractor rules
            if 'underleverandør' in chunk.get('title', '').lower():
                graph["subcontractor_rules"].append({
                    "risk_level": risk_levels,
                    "max_levels": self._extract_subcontractor_levels(chunk.get('content_text', ''))
                })
            
            # Process apprentice requirements
            if 'lærling' in chunk.get('title', '').lower():
                min_val = thresholds.get('min', 0)
                if min_val > 1000000:  # State threshold
                    graph["apprentice_requirements"]["threshold"] = min_val
                    graph["apprentice_requirements"]["required_codes"] = ["V"]
        
        return graph
    
    def _apply_constraints(self,
                          graph: Dict[str, Any],
                          procurement: ProcurementRequest,
                          chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Phase 3: Apply constraint satisfaction to determine applicable requirements.
        """
        applicable = set()
        
        # Add mandatory requirements
        applicable.update(graph["mandatory_requirements"])
        
        # Check value-based requirements
        for value_range, codes in graph["value_based_requirements"].items():
            min_val, max_val = value_range.split('-')
            min_val = int(min_val)
            max_val = float('inf') if max_val == 'inf' else int(max_val)
            
            if min_val <= procurement.value <= max_val:
                applicable.update(codes)
        
        # Assess risk and add risk-based requirements
        risk_assessment = self._assess_risk(procurement, chunks)
        if risk_assessment in ["moderat", "høy"]:
            applicable.update(graph["risk_based_requirements"].get("any_risk", []))
        
        # Check apprentice requirements
        if procurement.value > graph["apprentice_requirements"].get("threshold", float('inf')):
            if procurement.duration_months > 3:
                if self._involves_apprentice_trade(procurement):
                    applicable.update(graph["apprentice_requirements"].get("required_codes", []))
        
        return sorted(list(applicable))
    
    def _assess_risk(self, 
                    procurement: ProcurementRequest,
                    chunks: List[Dict[str, Any]]) -> str:
        """
        Assess risk level based on procurement characteristics and chunk metadata.
        """
        risk_score = 0
        
        # Value-based risk
        if procurement.value > 5000000:
            risk_score += 3
        elif procurement.value > 1000000:
            risk_score += 2
        elif procurement.value > 500000:
            risk_score += 1
        
        # Category-based risk
        if procurement.category.value in ["CONSTRUCTION", "CLEANING"]:
            risk_score += 2
        
        # International tender risk
        if procurement.international_tender:
            risk_score += 1
        
        # Check chunk metadata for risk indicators
        for chunk in chunks:
            risk_contexts = chunk.get('risk_context', [])
            if 'arbeidslivskriminalitet' in risk_contexts:
                risk_score += 1
                break
        
        # Determine risk level
        if risk_score >= 5:
            return "høy"
        elif risk_score >= 3:
            return "moderat"
        else:
            return "lav"
    
    def _determine_subcontractor_levels(self,
                                       risk_level: str,
                                       chunks: List[Dict[str, Any]]) -> int:
        """
        Determine allowed subcontractor levels based on risk.
        """
        # Check chunk rules first
        for chunk in chunks:
            if 'underleverandør' in chunk.get('title', '').lower():
                content = chunk.get('content_text', '')
                if risk_level == "høy" and "nektes bruk" in content:
                    return 0
                elif risk_level == "moderat" and "ett ledd" in content:
                    return 1
                elif risk_level == "lav" and "to ledd" in content:
                    return 2
        
        # Default rules
        if risk_level == "høy":
            return 0
        elif risk_level == "moderat":
            return 1
        else:
            return 2
    
    async def _generate_assessment(self,
                                  procurement: ProcurementRequest,
                                  applicable_requirements: List[str],
                                  chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 4: Generate final structured assessment.
        """
        # Assess risk
        risk_level = self._assess_risk(procurement, chunks)
        
        # Determine subcontractor levels
        subcontractor_levels = self._determine_subcontractor_levels(risk_level, chunks)
        
        # Check apprentice requirement
        requires_apprentices = (
            "V" in applicable_requirements and
            procurement.value > 1300000 and
            procurement.duration_months > 3
        )
        
        # Build structured prompt with metadata context
        context = self._build_metadata_context(chunks)
        
        prompt = f"""
        Basert på følgende strukturerte metadata og regler, generer Oslomodell assessment:
        
        ANSKAFFELSE:
        - Navn: {procurement.name}
        - Verdi: {procurement.value} NOK
        - Kategori: {procurement.category.value}
        - Varighet: {procurement.duration_months} måneder
        
        IDENTIFISERTE KRAV FRA METADATA:
        - Gjeldende kravkoder: {', '.join(applicable_requirements)}
        - Risikovurdering: {risk_level}
        - Underleverandørledd: {subcontractor_levels}
        - Lærlinger påkrevd: {'Ja' if requires_apprentices else 'Nei'}
        
        METADATA KONTEKST:
        {context}
        
        Generer strukturert JSON med:
        - required_requirements: Liste av requirement objekter (kun koder A-V)
        - crime_risk_assessment: "{risk_level}"
        - subcontractor_levels: {subcontractor_levels}
        - apprenticeship_requirement: Strukturert objekt
        - confidence: Din sikkerhet (0.0-1.0)
        """
        
        result = await self.llm_gateway.generate_structured(
            prompt=prompt,
            response_schema=OslomodellAssessmentResult.model_json_schema(),
            purpose="complex_reasoning",
            temperature=0.1
        )
        
        # Ensure requirements only have codes, not full descriptions
        if result.get('required_requirements'):
            simplified_requirements = []
            for req in result['required_requirements']:
                if isinstance(req, dict):
                    simplified_req = {
                        "code": req.get("code", "?"),
                        "name": f"Krav {req.get('code', '?')}",
                        "description": f"Oslomodell krav {req.get('code', '?')}",
                        "mandatory": True,
                        "source": "oslomodellen",
                        "category": "seriøsitet"
                    }
                    simplified_requirements.append(simplified_req)
            result['required_requirements'] = simplified_requirements
        
        # Add metadata
        result['procurement_id'] = procurement.id
        result['procurement_name'] = procurement.name
        result['assessment_date'] = datetime.now().isoformat()
        result['context_documents_used'] = [chunk.get('chunk_id', 'unknown') for chunk in chunks]
        result['confidence'] = self._calculate_confidence(chunks)
        
        return result
    
    def _extract_codes_from_description(self, description: str) -> List[str]:
        """
        Extract requirement codes from text description.
        """
        codes = []
        
        # Look for patterns like "krav A-E" or "A, B, C"
        import re
        
        # Pattern for ranges like A-E
        range_pattern = r'([A-V])-([A-V])'
        matches = re.findall(range_pattern, description.upper())
        for start, end in matches:
            start_ord = ord(start)
            end_ord = ord(end)
            for i in range(start_ord, end_ord + 1):
                codes.append(chr(i))
        
        # Pattern for individual codes
        individual_pattern = r'\b([A-V])\b'
        individual_matches = re.findall(individual_pattern, description.upper())
        codes.extend(individual_matches)
        
        return list(set(codes))  # Remove duplicates
    
    def _extract_subcontractor_levels(self, text: str) -> int:
        """
        Extract number of allowed subcontractor levels from text.
        """
        if "nektes bruk" in text.lower() or "0 ledd" in text:
            return 0
        elif "ett ledd" in text.lower() or "1 ledd" in text:
            return 1
        elif "to ledd" in text.lower() or "2 ledd" in text:
            return 2
        else:
            return 1  # Default
    
    def _involves_apprentice_trade(self, procurement: ProcurementRequest) -> bool:
        """
        Check if procurement involves trades requiring apprentices.
        """
        # Check description for trade keywords
        if procurement.description:
            desc_lower = procurement.description.lower()
            for trade in self.apprentice_trades:
                if trade in desc_lower:
                    return True
        
        # Construction always involves trades
        if procurement.category.value == "CONSTRUCTION":
            return True
        
        return False
    
    def _build_metadata_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Build context from chunk metadata for LLM.
        """
        context_parts = []
        
        for chunk in chunks[:5]:  # Top 5 chunks
            metadata_summary = f"""
            SEKSJON {chunk.get('section_number', '?')}: {chunk.get('title', '')}
            - Kravkoder: {', '.join(chunk.get('requirement_codes', []))}
            - Risikonivå: {', '.join(chunk.get('risk_level', []))}
            - Kategorier: {', '.join(chunk.get('applies_to_categories', []))}
            - Verdigrenser: {json.dumps(chunk.get('key_values_and_thresholds', {}))}
            """
            context_parts.append(metadata_summary.strip())
        
        return "\n\n".join(context_parts)
    
    def _calculate_confidence(self, chunks: List[Dict[str, Any]]) -> float:
        """
        Calculate confidence based on chunk quality and relevance.
        """
        if not chunks:
            return 0.3
        
        # Average of similarity and relevance scores
        scores = []
        for chunk in chunks[:5]:
            sim_score = chunk.get('similarity_score', 0)
            rel_score = chunk.get('relevance_score', 0)
            scores.append((sim_score + rel_score) / 2)
        
        if scores:
            avg_score = sum(scores) / len(scores)
            # Scale to 0.5-1.0 range
            return 0.5 + (avg_score * 0.5)
        
        return 0.5