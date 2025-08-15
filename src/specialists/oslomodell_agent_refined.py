# src/specialists/oslomodell_agent_refined.py
"""
Refined Oslomodell agent with multi-step process:
1. Initial Risk Assessment (LLM)
2. Dual-Path Filtering (Deterministic for rules, Semantic for context)
3. Final Comprehensive Assessment (LLM)

This version uses local JSON file for testing before database integration.
"""
import json
import asyncio
import structlog
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import uuid

from src.agent_library.core import BaseSpecialistAgent
from src.agent_library.registry import register_tool
from src.agent_library.decorators import build_metadata, with_schemas

from src.models import (
    OslomodellInput,
    OslomodellAssessment,
    Requirement,
    ApprenticeshipRequirement,
    RiskLevel,
    RiskType,
    DueDiligenceRequirement,
    RequirementSource,
    RequirementCategory,
    RequirementType
)

# Import new enums
from src.models.enums import (
    ChunkType,
    ConditionOperator
)

from src.tools.llm_gateway import LLMGateway

logger = structlog.get_logger()

OSLOMODELL_METADATA = build_metadata(
    description="Refined hybrid assessment combining deterministic rules with semantic context",
    input_schema_class=OslomodellInput,
    output_schema_class=OslomodellAssessment
)

@register_tool(
    name="agent.run_oslomodell_refined",
    service_type="specialist_agent",
    metadata=OSLOMODELL_METADATA,
    dependencies=["llm_gateway"],
    save_method="database.save_oslomodell_assessment"
)
@with_schemas(
    input_schema=OslomodellInput,
    output_schema=OslomodellAssessment
)
class RefinedOslomodellAgent(BaseSpecialistAgent):
    """
    Refined agent using multi-step process with local JSON for testing.
    """
    
    def __init__(self, chunks_file: str = "oslomodell_chunks_final.json"):
        super().__init__()
        self.chunks_file = chunks_file
        self.llm_gateway = None
        self.chunks_cache = None
        
    async def initialize(self):
        """Initialize LLM gateway and load chunks."""
        self.llm_gateway = LLMGateway()
        
        # Load chunks from local JSON file
        self.chunks_cache = await self._load_chunks_from_file()
        
        logger.info(
            "RefinedOslomodellAgent initialized",
            chunks_loaded=len(self.chunks_cache),
            source=self.chunks_file
        )
        
    async def _load_chunks_from_file(self) -> List[Dict[str, Any]]:
        """Load chunks from local JSON file for testing."""
        try:
            file_path = Path(self.chunks_file)
            if not file_path.exists():
                logger.error(f"Chunks file not found: {self.chunks_file}")
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            
            # Add chunk_type based on content if not present
            for chunk in chunks:
                if "chunk_type" not in chunk:
                    chunk["chunk_type"] = self._infer_chunk_type(chunk)
            
            logger.info(f"Loaded {len(chunks)} chunks from {self.chunks_file}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error loading chunks: {e}")
            return []
    
    def _infer_chunk_type(self, chunk: Dict[str, Any]) -> str:
        """Infer chunk type based on metadata if not explicitly set."""
        # Check if it has rule_sets - likely a RULE chunk
        if chunk.get("rule_sets"):
            return ChunkType.RULE.value
        
        # Check section number patterns
        section = chunk.get("section_number", "")
        if section in ["1", "2"]:  # Formål, Virkeområde
            return ChunkType.CONTEXT.value
        elif section in ["11", "12"]:  # Merking, Veiledning
            return ChunkType.GUIDANCE.value
        
        # Default to RULE for most instruction sections
        return ChunkType.RULE.value
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute refined assessment process.
        """
        try:
            procurement = OslomodellInput(**params)
            logger.info(f"Starting refined assessment for: {procurement.name}")
            
            # STEP 1: Initial risk assessment with LLM
            risk_profile = await self._assess_initial_risk(procurement)
            logger.info("Initial risk profile assessed", risk=risk_profile)
            
            # STEP 2: Get all chunks (from cache in this test version)
            all_chunks = self.chunks_cache or []
            logger.info(f"Using {len(all_chunks)} cached chunks")
            
            # STEP 3A: Deterministic filtering of rules
            applicable_rules = self._filter_applicable_rules(
                procurement, risk_profile, all_chunks
            )
            logger.info(
                f"Found {len(applicable_rules)} applicable rule sets",
                rule_sections=[r.get("source_section") for r in applicable_rules[:5]]
            )
            
            # STEP 3B: Semantic search for context
            semantic_context = self._find_semantic_context(
                procurement, risk_profile, all_chunks
            )
            logger.info(f"Found {len(semantic_context)} context snippets")
            
            # STEP 4: Comprehensive assessment with LLM
            final_assessment = await self._assess_with_llm(
                procurement, risk_profile, applicable_rules, semantic_context
            )
            
            # STEP 5: Build OslomodellAssessment object
            assessment = self._build_assessment(
                procurement, risk_profile, applicable_rules, final_assessment
            )
            
            return assessment.model_dump()
            
        except Exception as e:
            logger.error(f"Refined assessment failed: {str(e)}")
            raise
    
    async def _assess_initial_risk(self, procurement: OslomodellInput) -> Dict[str, str]:
        """
        Use LLM to make initial risk assessment of the procurement itself.
        """
        prompt = f"""
Analyser følgende anskaffelse og gi en kortfattet risikovurdering.
Fokuser på risiko for arbeidslivskriminalitet, sosial dumping og brudd på menneskerettigheter.

**Anskaffelse:**
- Navn: {procurement.name}
- Verdi: {procurement.value:,} NOK
- Kategori: {procurement.category.value}
- Varighet: {procurement.duration_months} måneder
- Beskrivelse: {procurement.description or 'Ikke oppgitt'}

Vurder risiko basert på:
1. Bransje (bygg/anlegg har typisk høyere risiko)
2. Kontraktsverdi (høyere verdi = mer attraktivt for useriøse)
3. Kompleksitet (mange underleverandører øker risiko)
4. Geografisk eksponering (internasjonale leverandører)

Returner et JSON-objekt med følgende struktur:
{{
    "labor_risk": "lav|moderat|høy",
    "social_dumping_risk": "lav|moderat|høy",
    "human_rights_risk": "lav|moderat|høy",
    "corruption_risk": "lav|moderat|høy",
    "supply_chain_complexity": "lav|moderat|høy",
    "risk_reasoning": "Kort begrunnelse for vurderingen"
}}
"""
        
        # For testing: Simuler LLM respons basert på kategori og verdi
        if not self.llm_gateway:
            # Fallback for testing without LLM
            return self._simulate_risk_assessment(procurement)
        
        try:
            response = await self.llm_gateway.complete(
                user_prompt=prompt,
                response_format={"type": "json_object"},
                temperature=0.3  # Low temperature for consistent risk assessment
            )
            return json.loads(response)
        except Exception as e:
            logger.warning(f"LLM risk assessment failed, using fallback: {e}")
            return self._simulate_risk_assessment(procurement)
    
    def _simulate_risk_assessment(self, procurement: OslomodellInput) -> Dict[str, str]:
        """Fallback risk assessment for testing without LLM."""
        # Simple rule-based risk assessment
        base_risk = "lav"
        
        if procurement.category.value in ["bygg", "anlegg", "renhold"]:
            base_risk = "moderat"
        
        if procurement.value > 5_000_000:
            base_risk = "høy"
        elif procurement.value > 1_000_000 and base_risk == "moderat":
            base_risk = "høy"
        
        return {
            "labor_risk": base_risk,
            "social_dumping_risk": base_risk,
            "human_rights_risk": "lav" if procurement.value < 10_000_000 else "moderat",
            "corruption_risk": "lav",
            "supply_chain_complexity": base_risk,
            "risk_reasoning": f"Vurdering basert på {procurement.category.value} med verdi {procurement.value:,} NOK"
        }
    
    def _filter_applicable_rules(
        self,
        procurement: OslomodellInput,
        risk_profile: Dict[str, str],
        all_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deterministic filtering of rule_sets from chunks.
        Returns only the rule_sets that match all conditions.
        """
        applicable_rule_sets = []
        
        for chunk in all_chunks:
            # Only process chunks with rule_sets
            rule_sets = chunk.get("rule_sets", [])
            if not rule_sets:
                continue
            
            for rule_set in rule_sets:
                conditions = rule_set.get("conditions", [])
                
                if self._evaluate_conditions_for_ruleset(
                    procurement, risk_profile, conditions
                ):
                    # Enrich rule_set with source information
                    enriched_rule = rule_set.copy()
                    enriched_rule["source_chunk_id"] = chunk.get("chunk_id")
                    enriched_rule["source_section"] = chunk.get("section_number")
                    enriched_rule["source_title"] = chunk.get("title")
                    applicable_rule_sets.append(enriched_rule)
                    
                    logger.debug(
                        "Rule set matched",
                        scenario=rule_set.get("scenario"),
                        section=chunk.get("section_number")
                    )
        
        return applicable_rule_sets
    
    def _evaluate_conditions_for_ruleset(
        self,
        procurement: OslomodellInput,
        risk_profile: Dict[str, str],
        conditions: List[Dict[str, Any]]
    ) -> bool:
        """
        Evaluate if all conditions for a rule set are met.
        """
        if not conditions:
            return True  # Empty conditions = always applicable
        
        for condition in conditions:
            if not self._evaluate_single_condition(
                procurement, risk_profile, condition
            ):
                return False
        
        return True
    
    def _evaluate_single_condition(
        self,
        procurement: OslomodellInput,
        risk_profile: Dict[str, str],
        condition: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single condition using the standardized operators.
        """
        field = condition.get("field")
        operator = condition.get("operator")
        expected_value = condition.get("value")
        
        # Get actual value based on field
        actual_value = self._get_field_value(procurement, risk_profile, field)
        
        if actual_value is None:
            logger.debug(f"Field {field} not found, skipping condition")
            return False
        
        # Normalize operator to enum if it's a string
        if operator in [">", ">=", "<", "<=", "=", "=="]:
            operator_map = {
                ">": ConditionOperator.GT,
                ">=": ConditionOperator.GTE,
                "<": ConditionOperator.LT,
                "<=": ConditionOperator.LTE,
                "=": ConditionOperator.EQ,
                "==": ConditionOperator.EQ
            }
            operator = operator_map.get(operator, operator)
        
        # Evaluate based on operator
        try:
            if operator in [ConditionOperator.GT, ">"]:
                return actual_value > expected_value
            elif operator in [ConditionOperator.GTE, ">="]:
                return actual_value >= expected_value
            elif operator in [ConditionOperator.LT, "<"]:
                return actual_value < expected_value
            elif operator in [ConditionOperator.LTE, "<="]:
                return actual_value <= expected_value
            elif operator in [ConditionOperator.EQ, "=", "equals"]:
                return actual_value == expected_value
            elif operator in [ConditionOperator.IN, "in"]:
                return actual_value in expected_value
            elif operator in [ConditionOperator.NOT_IN, "not_in"]:
                return actual_value not in expected_value
            elif operator in [ConditionOperator.BETWEEN, "between"]:
                return expected_value[0] <= actual_value <= expected_value[1]
            elif operator in [ConditionOperator.CONTAINS, "contains"]:
                return expected_value in str(actual_value)
            elif operator in [ConditionOperator.IS_TRUE, "is_true", "er_oppfylt"]:
                return bool(actual_value)
            elif operator in [ConditionOperator.IS_FALSE, "is_false"]:
                return not bool(actual_value)
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
                
        except (TypeError, KeyError, IndexError) as e:
            logger.warning(f"Error evaluating condition: {e}")
            return False
    
    def _get_field_value(
        self,
        procurement: OslomodellInput,
        risk_profile: Dict[str, str],
        field: str
    ) -> Any:
        """
        Get the actual value for a field from procurement or risk profile.
        """
        # Map field names to actual values
        field_lower = field.lower()
        
        # Procurement fields
        if field_lower in ["kontraktsverdi", "contractvalue", "value"]:
            return procurement.value
        elif field_lower in ["anskaffelsestype", "procurementcategory", "category"]:
            return procurement.category.value
        elif field_lower in ["varighet_måneder", "duration_months", "duration"]:
            return procurement.duration_months
        elif field_lower in ["includes_construction", "inkluderer_bygg"]:
            return procurement.includes_construction
        
        # Risk profile fields
        elif field_lower in ["risk_level", "risikonivå", "labor_risk"]:
            return risk_profile.get("labor_risk", "lav")
        elif field_lower == "social_dumping_risk":
            return risk_profile.get("social_dumping_risk", "lav")
        elif field_lower == "human_rights_risk":
            return risk_profile.get("human_rights_risk", "lav")
        
        # Special fields
        elif field_lower == "vilkår_krav_v":
            # Check if apprentice conditions are met
            return (procurement.value > 1_300_000 and 
                   procurement.duration_months > 3 and
                   procurement.category.value in ["bygg", "anlegg"])
        
        logger.debug(f"Field {field} not mapped, returning None")
        return None
    
    def _find_semantic_context(
        self,
        procurement: OslomodellInput,
        risk_profile: Dict[str, str],
        all_chunks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Find relevant context from non-rule chunks.
        In production, this would use semantic search.
        """
        context_snippets = []
        
        # Filter chunks that are context/guidance type
        context_chunks = [
            c for c in all_chunks
            if c.get("chunk_type") in [ChunkType.CONTEXT.value, ChunkType.GUIDANCE.value]
            or (not c.get("rule_sets") and c.get("section_number") in ["1", "2", "11", "12"])
        ]
        
        # For testing: Simple keyword matching
        keywords = [
            procurement.category.value,
            "arbeidslivskriminalitet" if risk_profile.get("labor_risk") != "lav" else "",
            "menneskerettigheter" if risk_profile.get("human_rights_risk") != "lav" else "",
            "aktsomhet" if procurement.value > 500_000 else ""
        ]
        keywords = [k for k in keywords if k]  # Remove empty
        
        for chunk in context_chunks:
            content = chunk.get("content", "").lower()
            if any(keyword.lower() in content for keyword in keywords):
                snippet = f"[{chunk.get('title', 'Ukjent')}]: {content[:300]}..."
                context_snippets.append(snippet)
        
        # Limit to top 3 most relevant
        return context_snippets[:3]
    
    async def _assess_with_llm(
        self,
        procurement: OslomodellInput,
        risk_profile: Dict[str, str],
        applicable_rules: List[Dict[str, Any]],
        semantic_context: List[str]
    ) -> Dict[str, Any]:
        """
        Final comprehensive assessment using LLM with all gathered information.
        """
        # Build rules summary
        rules_summary = self._build_rules_summary(applicable_rules)
        
        # Build context summary
        context_summary = "\n".join(semantic_context) if semantic_context else "Ingen spesiell kontekst funnet."
        
        prompt = f"""
**OPPGAVE: Helhetlig vurdering av anskaffelse mot Oslomodellen**

**1. ANSKAFFELSE:**
- Navn: {procurement.name}
- Verdi: {procurement.value:,} NOK
- Kategori: {procurement.category.value}
- Varighet: {procurement.duration_months} måneder
- Beskrivelse: {procurement.description or 'Ikke oppgitt'}

**2. INNLEDENDE RISIKOVURDERING:**
- Arbeidslivskriminalitet: {risk_profile.get('labor_risk')}
- Sosial dumping: {risk_profile.get('social_dumping_risk')}
- Menneskerettigheter: {risk_profile.get('human_rights_risk')}
- Begrunnelse: {risk_profile.get('risk_reasoning', 'Ikke oppgitt')}

**3. GJELDENDE REGLER (deterministisk identifisert):**
{rules_summary}

**4. RELEVANT KONTEKST:**
{context_summary}

**5. DIN OPPGAVE:**
Gjør en helhetlig vurdering med spesielt fokus på aktsomhetsvurderinger som er komplekse.
Gi en konsis men grundig vurdering som dekker alle aspekter.

Returner et JSON-objekt med følgende struktur:
{{
    "final_risk_assessment": {{
        "labor_crime": "ingen|lav|moderat|høy|kritisk",
        "social_dumping": "ingen|lav|moderat|høy|kritisk",
        "overall": "ingen|lav|moderat|høy|kritisk"
    }},
    "subcontractor_recommendation": {{
        "max_levels": 0-2,
        "justification": "Begrunnelse basert på risiko"
    }},
    "due_diligence_recommendation": {{
        "required": true/false,
        "set": "SET_A|SET_B|NONE",
        "justification": "Begrunnelse for valg av kravsett"
    }},
    "key_requirements": ["Liste over de viktigste kravkodene"],
    "special_considerations": ["Spesielle hensyn fra kontekst"],
    "recommendations": ["Konkrete anbefalinger"],
    "confidence": 0.0-1.0
}}
"""
        
        # For testing: Return simulated response if no LLM
        if not self.llm_gateway:
            return self._simulate_final_assessment(
                procurement, risk_profile, applicable_rules
            )
        
        try:
            response = await self.llm_gateway.complete(
                user_prompt=prompt,
                response_format={"type": "json_object"},
                temperature=0.4  # Balanced for nuanced assessment
            )
            return json.loads(response)
        except Exception as e:
            logger.warning(f"LLM final assessment failed, using fallback: {e}")
            return self._simulate_final_assessment(
                procurement, risk_profile, applicable_rules
            )
    
    def _build_rules_summary(self, applicable_rules: List[Dict[str, Any]]) -> str:
        """Build a formatted summary of applicable rules."""
        if not applicable_rules:
            return "Ingen spesifikke regler identifisert."
        
        summary_lines = []
        for rule in applicable_rules[:10]:  # Limit to avoid too long prompt
            codes = ", ".join(rule.get("applies_to_codes", []))
            scenario = rule.get("scenario", "Ukjent scenario")
            section = rule.get("source_section", "?")
            
            summary_lines.append(
                f"- Seksjon {section}: {scenario}\n"
                f"  Utløser krav: {codes if codes else 'Ingen spesifikke koder'}"
            )
        
        return "\n".join(summary_lines)
    
    def _simulate_final_assessment(
        self,
        procurement: OslomodellInput,
        risk_profile: Dict[str, str],
        applicable_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback assessment for testing without LLM."""
        # Extract all requirement codes from applicable rules
        all_codes = set()
        for rule in applicable_rules:
            all_codes.update(rule.get("applies_to_codes", []))
        
        # Determine subcontractor levels based on risk
        risk_level = risk_profile.get("labor_risk", "lav")
        if risk_level == "høy":
            max_levels = 0
        elif risk_level == "moderat":
            max_levels = 1
        else:
            max_levels = 2
        
        # Determine due diligence
        dd_required = procurement.value > 500_000 and risk_level in ["moderat", "høy"]
        dd_set = "SET_A" if dd_required and risk_level == "høy" else "SET_B" if dd_required else "NONE"
        
        return {
            "final_risk_assessment": {
                "labor_crime": risk_profile.get("labor_risk", "lav"),
                "social_dumping": risk_profile.get("social_dumping_risk", "lav"),
                "overall": risk_level
            },
            "subcontractor_recommendation": {
                "max_levels": max_levels,
                "justification": f"Basert på {risk_level} risiko"
            },
            "due_diligence_recommendation": {
                "required": dd_required,
                "set": dd_set,
                "justification": f"{'Påkrevd' if dd_required else 'Ikke påkrevd'} basert på verdi og risiko"
            },
            "key_requirements": sorted(list(all_codes)),
            "special_considerations": ["Vurder markedsdialog"],
            "recommendations": ["Følg standard prosedyrer"],
            "confidence": 0.7
        }
    
    def _build_assessment(
        self,
        procurement: OslomodellInput,
        risk_profile: Dict[str, str],
        applicable_rules: List[Dict[str, Any]],
        final_assessment: Dict[str, Any]
    ) -> OslomodellAssessment:
        """
        Build the final OslomodellAssessment object.
        """
        # Map risk strings to RiskLevel enum
        risk_map = {
            "ingen": RiskLevel.NONE,
            "lav": RiskLevel.LOW,
            "moderat": RiskLevel.MEDIUM,
            "høy": RiskLevel.HIGH,
            "kritisk": RiskLevel.CRITICAL
        }
        
        # Get risk assessments
        risk_data = final_assessment.get("final_risk_assessment", {})
        
        # Create requirements from codes
        requirements = []
        for code in final_assessment.get("key_requirements", []):
            requirements.append(Requirement(
                code=code,
                name=f"Oslomodell krav {code}",
                description=f"Krav {code} fra instruksen",
                mandatory=True,
                source=RequirementSource.OSLOMODELL,
                category=self._get_requirement_category(code)
            ))
        
        # Create apprenticeship requirement if needed
        apprenticeship = None
        if "V" in final_assessment.get("key_requirements", []):
            apprenticeship = ApprenticeshipRequirement(
                required=True,
                reason="Over terskelverdi og varighet i utførende fag",
                minimum_count=1,
                applicable_trades=["bygge", "anlegg"],
                threshold_exceeded=True
            )
        
        # Get due diligence
        dd_data = final_assessment.get("due_diligence_recommendation", {})
        dd_map = {
            "SET_A": DueDiligenceRequirement.SET_A,
            "SET_B": DueDiligenceRequirement.SET_B,
            "NONE": None
        }
        
        # Build assessment
        assessment = OslomodellAssessment(
            procurement_id=procurement.procurement_id,
            procurement_name=procurement.name,
            assessment_id=str(uuid.uuid4()),
            
            # Risk assessments
            labor_risk_assessment=risk_map.get(
                risk_data.get("labor_crime", "lav"), RiskLevel.LOW
            ),
            social_dumping_risk=risk_map.get(
                risk_data.get("social_dumping", "lav"), RiskLevel.LOW
            ),
            rights_risk_assessment=risk_map.get(
                risk_profile.get("human_rights_risk", "lav"), RiskLevel.LOW
            ),
            corruption_risk=risk_map.get(
                risk_profile.get("corruption_risk", "lav"), RiskLevel.LOW
            ),
            occupation_risk=RiskLevel.LOW,
            international_law_risk=RiskLevel.LOW,
            environment_risk=RiskLevel.LOW,
            
            # Requirements
            required_requirements=requirements,
            
            # Subcontractors
            subcontractor_levels=final_assessment.get(
                "subcontractor_recommendation", {}
            ).get("max_levels", 2),
            subcontractor_justification=final_assessment.get(
                "subcontractor_recommendation", {}
            ).get("justification", "Standard vurdering"),
            
            # Apprenticeship
            apprenticeship_requirement=apprenticeship,
            
            # Due diligence
            due_diligence_requirement=dd_map.get(dd_data.get("set")),
            
            # Metadata
            applicable_instruction_points=[
                r.get("source_section") for r in applicable_rules
                if r.get("source_section")
            ][:10],  # Limit to 10
            identified_risk_areas=[
                k.replace("_", " ") for k, v in risk_profile.items()
                if v in ["moderat", "høy"] and k.endswith("_risk")
            ],
            
            # Confidence and reasoning
            confidence_score=final_assessment.get("confidence", 0.8),
            chunks_used=[r.get("source_chunk_id") for r in applicable_rules][:20],
            context_documents_used=["Instruks for Oslo kommunes anskaffelser"],
            reasoning=final_assessment.get("special_considerations", []),
            recommendations=final_assessment.get("recommendations", []),
            warnings=[]
        )
        
        # Add warnings for high risk
        if risk_data.get("overall") in ["høy", "kritisk"]:
            assessment.warnings.append(
                f"Høy risiko identifisert - ekstra oppmerksomhet påkrevd"
            )
        
        return assessment
    
    def _get_requirement_category(self, code: str) -> RequirementCategory:
        """Map requirement code to category."""
        if code in ["A", "B", "C", "D", "E"]:
            return RequirementCategory.INTEGRITY
        elif code == "V":
            return RequirementCategory.APPRENTICES
        elif code in ["F", "G", "H"]:
            return RequirementCategory.DOCUMENTATION
        else:
            return RequirementCategory.OTHER