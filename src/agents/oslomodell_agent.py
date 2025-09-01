# src/agents/oslomodell_agent.py
import json
import uuid
import asyncio
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from datetime import datetime

import httpx
import structlog
from pydantic import ValidationError

# Importer nødvendige verktøy og modeller
from src.services.llm_gateway import LLMGateway, ParallelRequest, ParallelResponse
from src.models.base_models import (
    BaseProcurementInput, BaseAssessment, Rule, Requirement, Condition, RiskAssessmentItem
)
from src.models.enums import ConditionOperator, RiskType, RiskLevel
from src.models.llm_models import LLMRiskAssessmentOutput

# Stubs for spesialistagenter
from .apprentice_agent import ApprenticeAgent, RelevantTradesResponse
from .obs_list_agent import ObsListAgent, VerificationStatus
from ..analyzers.company_analyzer import CompanyAnalyzer

from src.services.brreg_service import BrregService

logger = structlog.get_logger()

class OslomodellAgent:
    # ... __init__ og _load_knowledge_base er uendret ...
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._load_knowledge_base()

        self.apprentice_agent = ApprenticeAgent(config)

        self.llm_gateway = LLMGateway()

        self.http_client = httpx.AsyncClient(timeout=10.0)

        self.brreg_service = BrregService(
        http_client=self.http_client,
        enhetsregisteret_url=config["external_services"]["brreg_enhetsregisteret_url"],
        regnskapsregisteret_url=config["external_services"]["brreg_regnskapsregisteret_url"],
        fullmakt_api_url=config["external_services"]["brreg_fullmakt_api_url"]
        )
    
        self.company_analyzer = CompanyAnalyzer(config.get("company_analyzer_config", {}))
        self.obs_agent = ObsListAgent(self.brreg_service, "data/OBS_listen.csv")

    def _load_knowledge_base(self):
        """
        Laster regler og krav fra JSON-kunnskapsbasen.
        Itererer gjennom ALLE chunks for å samle regler.
        """
        kb_file = self.config['knowledge_base']['file_path']
        logger.info("loading_knowledge_base", file=kb_file)
        
        try:
            with open(kb_file, 'r', encoding='utf-8') as f:
                knowledge_data = json.load(f)
                # Anta at metadata og krav-definisjoner ligger i den første chunken
                doc_metadata = knowledge_data[0].get('document_metadata', {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("knowledge_base_load_failed", error=str(e))
            raise IOError(f"Kunne ikke laste eller parse kunnskapsbase: {kb_file}") from e

        # Iterer gjennom ALLE chunks og samle regler
        self.rules: List[Rule] = []
        for chunk in knowledge_data:
            for rule_dict in chunk.get('rules', []):
                try:
                    self.rules.append(Rule.model_validate(rule_dict))
                except ValidationError as e:
                    logger.warning("rule_validation_failed", 
                                 rule_id=rule_dict.get('rule_id'), 
                                 chunk_id=chunk.get('chunk_id'), 
                                 error=str(e))

        # Krav-definisjoner lastes fortsatt fra den første chunken
        self.requirements: Dict[str, Requirement] = {}
        if doc_metadata:
            self.requirements = {
                req['code']: Requirement.model_validate(req)
                for req in doc_metadata.get('document_level_requirements', [])
            }
        
        if not self.rules or not self.requirements:
            raise ValueError("Kunnskapsbasen mangler regler eller krav-definisjoner.")

        logger.info("knowledge_base_loaded", 
                    rules_count=len(self.rules), 
                    requirements_count=len(self.requirements))

    async def assess(self, procurement: BaseProcurementInput) -> BaseAssessment:
        logger.info("assessment_started", procurement_id=procurement.procurement_id)

        # ======================================================================
        # STEG 1: LEVERANDØR-VERIFISERING (HVIS SPESIFISERT)
        # ======================================================================
        if procurement.supplier_name_to_verify:
            verification_result = await self.obs_agent.verify_supplier(
                supplier_name=procurement.supplier_name_to_verify,
                is_foreign=procurement.supplier_is_foreign
            )

            # Håndter de ulike utfallene fra verifiseringen
            if verification_result.status != VerificationStatus.OK:
                # Hvis verifiseringen ikke er OK, avbryter vi og returnerer en
                # spesialisert rapport som forklarer problemet.
                return self._create_verification_failed_assessment(procurement, verification_result)
            
            # Verifisering var OK, lagre det bekreftede org.nr. for senere bruk
            procurement.verified_supplier_orgnr = verification_result.metadata.get('organisasjonsnummer')
            logger.info("supplier_verification_successful", orgnr=procurement.verified_supplier_orgnr)

            # ======================================================================
            # KJØR SELSKAPSANALYSE
            # ======================================================================
            if procurement.verified_supplier_orgnr:
                log = logger.bind(orgnr=procurement.verified_supplier_orgnr)
                log.info("running_company_analysis")
                
                # Hent all data og analyser den
                comprehensive_data = await self.brreg_service.get_comprehensive_company_info(procurement.verified_supplier_orgnr)
                analysis_result = self.company_analyzer.analyze(comprehensive_data)
                
                # Lagre analysen i input-objektet for senere bruk
                procurement.company_analysis = analysis_result
                log.info("company_analysis_completed")


        # ======================================================================
        # STEG 2: FULL RISIKOVURDERING (Kjøres kun hvis leverandørsjekk er OK eller ikke ble bedt om)
        # ======================================================================

        # Steg 1: Utfør innledende, statisk risikovurdering
        self._perform_initial_risk_assessment(procurement)

        # Steg 2: Kjør sentralisert, parallell LLM-vurdering
        # Denne metoden returnerer nå en tuple
        llm_risk_items, apprentice_assessment_result = await self._run_parallel_risk_assessments(procurement)
        
        # Legg til de returnerte risikovurderingene i anskaffelsen for regelmotoren
        procurement.risk_assessments.extend(llm_risk_items)

        # Steg 3: Behandle og slå sammen resultatene
        specialist_assessments: List[BaseAssessment] = []
        if apprentice_assessment_result:
            specialist_assessments.append(apprentice_assessment_result)
        
        # Steg 4: Utfør den endelige regelevalueringen
        rule_engine_assessment = await self._evaluate_rules(procurement)
        
        all_assessments = [rule_engine_assessment] + specialist_assessments
        final_assessment = self._merge_assessments(procurement, all_assessments)

        # === START NY LOGIKK FOR FASE 3: OPPSUMMERING ===
        synthesis_config = self.config.get('synthesis_agent_config', {})
        if synthesis_config.get('enabled', False):
            logger.info("generating_final_summary", assessment_id=final_assessment.assessment_id)
            
            # 1. Forbered input-strenger for prompten
            
            # NYTT: Bygg en streng med kontekst om selve anskaffelsen
            procurement_context_str = (
                f"- Navn: {procurement.name}\n"
                f"- Kategori: {procurement.category.value}\n"
                f"- Beskrivelse: {procurement.description}"
            )

            # Bygg strengen med risikofunn (som før, men nå med rikere data)
            risk_summary_lines = []
            for item in procurement.risk_assessments:
                line = f"- **{item.type.value.replace('-', ' ').capitalize()}: {item.level.value.capitalize()}**"
                if item.justification:
                    line += f"\n  - *Begrunnelse fra spesialist:* {item.justification}"
                risk_summary_lines.append(line)
            risk_summary_str = "\n".join(risk_summary_lines) if risk_summary_lines else "Ingen spesifikke risikoer vurdert."

            # 2. Bygg den endelige, kontekstrike prompten
            prompt_template = synthesis_config.get('prompt', '')
            full_prompt = prompt_template.format(
                procurement_context=procurement_context_str, # <--- Ny variabel
                risk_assessments_summary=risk_summary_str
            )

            # 3. Kall LLM-gatewayen (merk: vi bruker .generate() for ren tekst)
            llm_params = synthesis_config.get('llm_parameters', {})
            summary_text = await self.llm_gateway.generate(
                prompt=full_prompt,
                purpose=llm_params.get('purpose', 'default'),
                **{'include_thoughts': llm_params.get('include_thoughts', False)}
            )

            # 4. Lagre resultatet i assessment-objektet
            final_assessment.summary_prose = summary_text
            
            # Oppdater anbefalingene for å inkludere den nye oppsummeringen
            # Dette er en fin måte å vise den i den eksisterende rapport-utskriften
            if final_assessment.recommendations:
                final_assessment.recommendations.insert(0, "--- HOVEDFUNN ---")
                final_assessment.recommendations.insert(1, summary_text)
            else:
                final_assessment.recommendations.append("--- HOVEDFUNN ---")
                final_assessment.recommendations.append(summary_text)

        # === SLUTT NY LOGIKK FOR FASE 3 ===

        logger.info("assessment_finished", assessment_id=final_assessment.assessment_id)
        return final_assessment

    async def _run_parallel_risk_assessments(self, procurement: BaseProcurementInput) -> tuple[List[RiskAssessmentItem], Optional[BaseAssessment]]: # <--- OPPDATER RETURTYPE
        """
        Samler, kjører og behandler alle LLM-baserte vurderinger parallelt.
        Returnerer en tuple: (liste med LLM-risikovurderinger, lærling-vurderingsobjekt).
        """
        requests: List[ParallelRequest] = []

        # === START LOGIKK FOR LÆRLING ===
        apprentice_config = self.config.get('apprentice_agent_config', {})
        llm_apprentice_config = apprentice_config.get('llm', {})

        # Portvokter-sjekk: Utfør kun LLM-kall hvis terskelverdier er møtt.
        if (llm_apprentice_config.get('enabled') and
            procurement.value >= apprentice_config.get('threshold_value', 0) and
            procurement.duration_months >= apprentice_config.get('min_duration_months', 0)):

            llm_params = llm_apprentice_config.get('llm_parameters', {})
            prompt_template = llm_apprentice_config.get('prompt_extract_trades', '')
            
            # Bygg prompten (logikk hentet fra apprentice_agent.py)
            valid_trades = list(self.apprentice_agent.udir_data_specific_trades.keys())
            full_prompt = (
                f"{prompt_template}\n\n"
                "Her er dataen for denne spesifikke anskaffelsen:\n"
                f"```json\n"
                f"{json.dumps({'description': procurement.description, 'valid_trades': valid_trades}, ensure_ascii=False, indent=2)}\n"
                f"```"
            )

            requests.append(ParallelRequest(
                id="apprentice_trades", # Unik ID for å identifisere responsen
                prompt=full_prompt,
                response_schema=RelevantTradesResponse, # Bruk Pydantic-modellen
                purpose=llm_params.get('purpose', 'default'),
                kwargs={'include_thoughts': llm_params.get('include_thoughts', False)}
            ))

        # === START LOGIKK FOR MENNESKERETTIGHETER OG HUMANITÆRRETT ===
        hr_config = self.config.get('human_rights_and_law_agent_config', {})
        if hr_config.get('enabled', False):
            
            # Hent LLM-parametere fra den nye konfigurasjonsseksjonen
            llm_params = hr_config.get('llm_parameters', {})
            purpose = llm_params.get('purpose', 'default')
            kwargs = {'include_thoughts': llm_params.get('include_thoughts', False)}

            # Bygg den nye, rike prompten med all relevant informasjon
            prompt = hr_config['prompt'].format(
                procurement_name=procurement.name,
                procurement_category=procurement.category.value,
                procurement_subcategory=procurement.subcategory.value if procurement.subcategory else "N/A",
                procurement_description=procurement.description or "Ingen detaljert beskrivelse.",
                procurement_value=procurement.value
            )
            
            requests.append(ParallelRequest(
                id="menneskerettigheter-og-folkerett",
                prompt=prompt,
                response_schema=LLMRiskAssessmentOutput,
                purpose=purpose, # Bruk purpose fra config
                kwargs=kwargs      # Send med 'include_thoughts'
            ))

        # === START LOGIKK FOR KORRUPSJON ===
        corruption_config = self.config.get('corruption_agent_config', {})
        if corruption_config.get('enabled', False):
            llm_params = corruption_config.get('llm_parameters', {})
            purpose = llm_params.get('purpose', 'default')
            kwargs = {'include_thoughts': llm_params.get('include_thoughts', False)}

            prompt = corruption_config['prompt'].format(
                procurement_name=procurement.name,
                procurement_category=procurement.category.value,
                procurement_subcategory=procurement.subcategory.value if procurement.subcategory else "N/A",
                procurement_description=procurement.description or "Ingen detaljert beskrivelse.",
                procurement_value=procurement.value
            )
            
            requests.append(ParallelRequest(
                id="korrupsjon",  # ID matcher RiskType enum-verdi
                prompt=prompt,
                response_schema=LLMRiskAssessmentOutput,
                purpose=purpose,
                kwargs=kwargs
            ))

        # === START LOGIKK FOR MILJØ ===
        environment_config = self.config.get('environment_agent_config', {})
        if environment_config.get('enabled', False):
            llm_params = environment_config.get('llm_parameters', {})
            purpose = llm_params.get('purpose', 'default')
            kwargs = {'include_thoughts': llm_params.get('include_thoughts', False)}

            prompt = environment_config['prompt'].format(
                procurement_name=procurement.name,
                procurement_category=procurement.category.value,
                procurement_subcategory=procurement.subcategory.value if procurement.subcategory else "N/A",
                procurement_description=procurement.description or "Ingen detaljert beskrivelse.",
                procurement_value=procurement.value
            )
            
            requests.append(ParallelRequest(
                id="miljø",  # ID matcher RiskType enum-verdi
                prompt=prompt,
                response_schema=LLMRiskAssessmentOutput,
                purpose=purpose,
                kwargs=kwargs
            ))

        if not requests:
            return [], None

        logger.info("sending_parallel_risk_requests_to_llm", count=len(requests))
        responses = await self.llm_gateway.generate_parallel(requests)

        # Behandle resultatene
        risk_items: List[RiskAssessmentItem] = []
        apprentice_assessment_result: Optional[BaseAssessment] = None # Ny variabel

        for response in responses:
            if not response.success:
                logger.error("llm_risk_assessment_failed", request_id=response.id, error=response.error)
                continue

            # === START NY LOGIKK FOR LÆRLING-RESULTAT ===
            if response.id == "apprentice_trades":
                # LLM returnerer en liste med fagområder.
                # Vi kaller en ny hjelpemetode på apprentice_agent for å bygge
                # det endelige assessment-objektet basert på dette resultatet.
                try:
                    trades_list = response.result.get('relevante_fagomraader', [])
                    # Valider at fagene er gyldige
                    validated_trades = [trade for trade in trades_list if trade in self.apprentice_agent.udir_data_specific_trades]
                    
                    if validated_trades:
                         apprentice_assessment_result = self.apprentice_agent.create_assessment_from_llm_result(
                            procurement, 
                            validated_trades
                         )
                except Exception as e:
                    logger.error("failed_to_create_apprentice_assessment_from_llm", error=str(e))

            # === SLUTT NY LOGIKK FOR LÆRLING-RESULTAT ===
            else: # Standard håndtering for risikovurderinger

                try:
                    risk_type = RiskType(response.id)
                    risk_level = RiskLevel(response.result['risk_level'])
                    justification = response.result['justification']
                    
                    risk_items.append(RiskAssessmentItem(type=risk_type, level=risk_level, justification=justification))
                    logger.info("llm_risk_assessment_successful", 
                                risk_type=risk_type.value, 
                                level=risk_level.value, 
                                justification=justification)
                except (ValueError, KeyError) as e:
                     logger.error("failed_to_parse_llm_risk_response", request_id=response.id, error=str(e))
        
        return risk_items, apprentice_assessment_result # <--- OPPDATER RETURVERDI

    def _perform_initial_risk_assessment(self, procurement: BaseProcurementInput):
        """Henter risikodata fra config og legger til i procurement-objektet."""
        mock_config = self.config.get('mock_risk_assessment', {})
        category_str = procurement.category.value
        
        risk_assessments_data = mock_config.get(category_str, [])
        
        if risk_assessments_data:
            procurement.risk_assessments = [
                RiskAssessmentItem.model_validate(item) for item in risk_assessments_data
            ]
        
        logger.info("procurement_enriched_with_mock_risk",
                    assessments_count=len(procurement.risk_assessments))

    async def _evaluate_rules(self, procurement: BaseProcurementInput) -> BaseAssessment:
        """
        Kjernen i regelmotoren. Evaluerer alle regler i en prioritert
        rekkefølge for å håndtere avhengigheter og overstyringer korrekt.
        """
        log = logger.bind(procurement_id=procurement.procurement_id)
        log.info("evaluating_declarative_rules")

        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)
        
        triggered_rules_map: Dict[str, Rule] = {}
        activated_codes: Set[str] = set()
        reasoning_steps = ["**Regel-evaluering startet (sortert etter prioritet)**"]
        overridden_by_map: Dict[str, str] = {}

        for rule in sorted_rules:
            if not rule.is_active():
                continue

            if rule.rule_id in overridden_by_map:
                reasoning_steps.append(f"✗ Regel '{rule.rule_id}' ble hoppet over fordi den ble overstyrt av '{overridden_by_map[rule.rule_id]}'.")
                continue

            is_triggered, reason = self._check_conditions_for_rule(rule, procurement, activated_codes)
            
            if is_triggered:
                triggered_rules_map[rule.rule_id] = rule
                activated_codes.update(rule.activates_requirement_codes)
                
                log.info("rule_triggered", rule_id=rule.rule_id, activates=rule.activates_requirement_codes)
                reasoning_steps.append(f"✓ Regel '{rule.rule_id}' (Prio: {rule.priority}) ble utløst: {reason}")

                if rule.overrides_rules:
                    for overridden_id in rule.overrides_rules:
                        overridden_by_map[overridden_id] = rule.rule_id
                        reasoning_steps.append(f"  - Informasjon: Regel '{rule.rule_id}' overstyrer '{overridden_id}'.")
            else:
                if reason:
                    reasoning_steps.append(f"✗ Regel '{rule.rule_id}' (Prio: {rule.priority}) ble ikke utløst: {reason}")
        
        final_triggered_rules = [rule for rule_id, rule in triggered_rules_map.items() if rule_id not in overridden_by_map]
        
        final_activated_codes = set()
        for rule in final_triggered_rules:
            final_activated_codes.update(rule.activates_requirement_codes)

        final_activated_codes, reasoning_steps = self._handle_tax_certificate_rules(
            procurement, final_activated_codes, reasoning_steps)

        applicable_requirements = [
            self.requirements[code] for code in sorted(list(final_activated_codes)) if code in self.requirements
        ]
        
        reasoning_steps.append(f"**Konklusjon regel-evaluering:** {len(applicable_requirements)} krav ble aktivert etter håndtering av prioriteter og overstyringer.")

        return BaseAssessment(
            procurement_id=procurement.procurement_id,
            procurement_name=procurement.name,
            agent_name="oslomodell_rule_engine",
            confidence_score=1.0,
            triggered_rules=final_triggered_rules,
            applicable_requirements=applicable_requirements,
            reasoning_steps=reasoning_steps
        )

    def _check_conditions_for_rule(self, rule: Rule, procurement: BaseProcurementInput, activated_codes: Set[str]) -> (bool, str):
        """
        Sjekker alle conditions for en gitt regel.
        """
        results = []
        # Lag en felles kontekst som inneholder all nødvendig informasjon
        context = procurement.model_dump()
        context['kontraktsvarighet_år'] = context.get('duration_months', 0) / 12
        context['activated_codes'] = activated_codes

        for cond in rule.conditions:
            evaluators = {
                "anskaffelsestype": self._eval_category,
                "kontraktsverdi": self._eval_value,
                "risiko": self._eval_risk_condition,
                "varighet_måneder": self._eval_duration_months,
                "kontraktsvarighet_år": self._eval_duration_years,
                "fase": self._eval_phase,
                "referanse": self._eval_reference,
                "kvalitativ_betingelse": self._eval_qualitative,
                "standardkontrakt_dekning": self._eval_standard_contract,
                "krav_aktivert": self._eval_requirement_activated,
                "subcategory": self._eval_subcategory
            }
            
            eval_func = evaluators.get(cond.field)
            if eval_func:
                result, reason_part = eval_func(cond, context)
                results.append((result, reason_part))
            else:
                results.append((False, f"Betingelse for '{cond.field}' er ikke implementert."))

        if not results:
            return True, "Regelen har ingen betingelser."

        if rule.condition_logic == "AND":
            final_result = all(r[0] for r in results)
            failed_reasons = [r[1] for r in results if not r[0]]
            reason = "Alle betingelser møtt." if final_result else f"Ikke alle betingelser møtt: {'; '.join(failed_reasons)}"
        else: # OR
            final_result = any(r[0] for r in results)
            if final_result:
                success_reasons = [r[1] for r in results if r[0]]
                reason = f"Minst én betingelse møtt: {'; '.join(success_reasons)}"
            else:
                failed_reasons = [r[1] for r in results]
                reason = f"Ingen betingelser møtt: {'; '.join(failed_reasons)}"
            
        return final_result, reason

    # --- Condition Evaluator-metoder ---
    def _eval_category(self, cond, context):
        actual = context.get('category')
        if not actual: return False, "anskaffelsestype mangler."
        expected_values = [v.value for v in (cond.value if isinstance(cond.value, list) else [cond.value])]
        
        if cond.operator == ConditionOperator.IN and actual in expected_values:
            return True, f"anskaffelsestype er '{actual}' (som er i listen)."
        return False, f"anskaffelsestype er '{actual}' (ikke i listen {expected_values})."

    def _eval_subcategory(self, cond, context):
        """Evaluerer betingelser basert på anskaffelsens underkategori."""
        actual_value = context.get('subcategory')
        
        if not actual_value:
            return False, "" 
        
        expected_values = [v.value for v in (cond.value if isinstance(cond.value, list) else [cond.value])]

        if cond.operator == ConditionOperator.IN and actual_value in expected_values:
            return True, f"subcategory er '{actual_value}' (som er i listen)."
        
        return False, f"subcategory er '{actual_value}' (ikke i listen {expected_values})."

    def _eval_value(self, cond, context):
        actual = context.get('value')
        if actual is None: return False, "kontraktsverdi mangler."
        expected = cond.value
        
        if cond.operator == ConditionOperator.BETWEEN:
            if not (isinstance(expected, list) and len(expected) == 2):
                return False, f"Ugyldig verdi for BETWEEN-operator: {expected}"
            res = expected[0] <= actual <= expected[1]
            return res, f"kontraktsverdi {actual} er mellom {expected[0]} og {expected[1]} er {res}."
        
        if not isinstance(expected, (int, float)):
            return False, f"Ugyldig verdi for operator '{cond.operator.value}': {expected}"

        op_map = {
            ConditionOperator.GT: actual > expected,
            ConditionOperator.GTE: actual >= expected,
            ConditionOperator.LT: actual < expected,
            ConditionOperator.LTE: actual <= expected,
            ConditionOperator.EQ: actual == expected,
        }
        if cond.operator in op_map:
            res = op_map[cond.operator]
            return res, f"kontraktsverdi {actual} {cond.operator.value} {expected} er {res}."
        
        return False, f"Ukjent operator '{cond.operator}' for kontraktsverdi."

    def _eval_risk_condition(self, cond, context):
        """
        Evaluerer den nye, presise risikobetingelsen ved å sjekke listen
        av risikovurderingsobjekter.
        """
        procurement_assessments = context.get('risk_assessments', [])
        if not procurement_assessments:
            return False, "ingen risikovurderinger er gjort for anskaffelsen."

        # Gå gjennom hver risikovurdering for anskaffelsen
        for assessment in procurement_assessments:
            # Sjekk om vurderingen matcher betingelsen i regelen
            type_matches = assessment['type'] in [t.value for t in cond.risk_types]
            level_matches = assessment['level'] in [l.value for l in cond.risk_levels]

            if type_matches and level_matches:
                # For CONTAINS_ANY, er én enkelt match nok
                return True, f"fant en match på risikotype '{assessment['type']}' med nivå '{assessment['level']}'."

        # Hvis vi kommer hit, ble ingen match funnet
        return False, "ingen av risikovurderingene møtte de påkrevde betingelsene."

    def _eval_duration_months(self, cond, context):
        """Evaluerer betingelser basert på varighet i måneder."""
        actual = context.get('duration_months')
        if actual is None: return False, "varighet_måneder mangler."
        expected = cond.value
        
        if not isinstance(expected, (int, float)):
            return False, f"Ugyldig verdi for varighet_måneder: {expected}"

        op_map = {
            ConditionOperator.GT: actual > expected,
            ConditionOperator.GTE: actual >= expected,
            ConditionOperator.LT: actual < expected,
            ConditionOperator.LTE: actual <= expected,
            ConditionOperator.EQ: actual == expected,
        }
        if cond.operator in op_map:
            res = op_map[cond.operator]
            return res, f"varighet_måneder {actual} {cond.operator.value} {expected} er {res}."
        
        return False, f"Ukjent operator '{cond.operator}' for varighet_måneder."

    def _eval_duration_years(self, cond, context):
        """Evaluerer betingelser basert på varighet i år."""
        actual = context.get('kontraktsvarighet_år')
        if actual is None: return False, "kontraktsvarighet_år mangler."
        expected = cond.value
        
        if not isinstance(expected, (int, float)):
            return False, f"Ugyldig verdi for kontraktsvarighet_år: {expected}"

        op_map = {
            ConditionOperator.LT: actual < expected,
        }
        if cond.operator in op_map:
            res = op_map[cond.operator]
            return res, f"kontraktsvarighet_år {actual:.2f} {cond.operator.value} {expected} er {res}."
        
        return False, f"Ukjent operator '{cond.operator}' for kontraktsvarighet_år."

    def _eval_phase(self, cond, context):
        """Evaluerer betingelser basert på anskaffelsesfase."""
        current_phase = "planlegging"
        expected = cond.value.value if hasattr(cond.value, 'value') else cond.value

        if current_phase == expected:
            return True, f"anskaffelsesfase er '{current_phase}'."
        return False, f"anskaffelsesfase er '{current_phase}', ikke '{expected}'."

    def _eval_reference(self, cond, context):
        """
        Evaluerer 'referanse'. Dette er en kvalitativ sjekk.
        For nå returnerer vi False, da agenten ikke kan tolke referanser til andre dokumentpunkter.
        """
        reason = f"Betingelse basert på referanse ('{cond.value}') krever manuell tolkning og kan ikke evalueres automatisk."
        return False, reason

    def _eval_qualitative(self, cond, context):
        """
        Evaluerer 'kvalitativ_betingelse'.
        Dette krever typisk en LLM eller manuell input. Vi returnerer False.
        """
        reason = f"Kvalitativ betingelse ('{cond.value}') krever en avansert vurdering (f.eks. LLM) som ikke er implementert."
        return False, reason

    def _eval_standard_contract(self, cond, context):
        """
        Evaluerer om anskaffelsen dekkes av en standardkontrakt.
        Dette ville vært en boolsk verdi i inputen. Vi antar False for nå.
        """
        is_covered = context.get('standard_contract_coverage', False)
        
        if cond.operator == ConditionOperator.IS_TRUE and is_covered:
            return True, "anskaffelsen er dekket av standardkontrakt."
        if cond.operator == ConditionOperator.IS_FALSE and not is_covered:
            return True, "anskaffelsen er IKKE dekket av standardkontrakt."
            
        return False, f"sjekk for standardkontrakt (forventet: {cond.operator.value}, faktisk: {is_covered}) feilet."

    def _eval_requirement_activated(self, cond, context):
        activated_codes = context.get('activated_codes', set())
        
        required_codes = set([cond.value] if isinstance(cond.value, str) else cond.value)
        
        op = cond.operator
        if op == ConditionOperator.IN:
            is_met = not required_codes.isdisjoint(activated_codes)
            reason = f"krav '{next(iter(required_codes))}' er aktivert er {is_met}."
            return is_met, reason
        elif op == ConditionOperator.NOT_IN:
            is_met = required_codes.isdisjoint(activated_codes)
            reason = f"krav '{next(iter(required_codes))}' IKKE er aktivert er {is_met}."
            return is_met, reason
        
        return False, f"Ukjent operator '{op}' for krav_aktivert."

    def _handle_tax_certificate_rules(
        self,
        procurement: BaseProcurementInput,
        activated_codes: Set[str],
        reasoning_steps: List[str]
    ) -> (Set[str], List[str]):
        """
        Håndterer den spesifikke og prioriterte logikken for skatteattestkrav.
        Denne kjøres etter at alle JSON-regler er evaluert.
        """
        reasoning_steps.append("**Post-processing: Evaluerer skatteattestkrav**")
        
        if "T" in activated_codes:
            reasoning_steps.append("✓ Krav T er aktivert, utløser krav om utvidet skatteattest (SKATT-UTV).")
            activated_codes.add("SKATT-UTV")
            activated_codes.discard("SKATT-STD")
            return activated_codes, reasoning_steps

        if procurement.value > 500000:
            reasoning_steps.append("✓ Verdi > 500k og Krav T er ikke aktivt, utløser standard skatteattestkrav (SKATT-STD).")
            activated_codes.add("SKATT-STD")
            return activated_codes, reasoning_steps
            
        reasoning_steps.append("✗ Ingen betingelser for skatteattestkrav ble møtt.")
        return activated_codes, reasoning_steps

    def _merge_assessments(self, procurement: BaseProcurementInput, results: List[Any]) -> BaseAssessment:
        """
        Slår sammen resultater fra alle agenter til én samlet BaseAssessment.
        """
        final = BaseAssessment(
            assessment_id=str(uuid.uuid4()),
            procurement_id=procurement.procurement_id,
            procurement_name=procurement.name,
            agent_name="oslomodell_orchestrator",
            confidence_score=1.0, 
        )

        all_triggered_rules: Dict[str, Rule] = {} 
        all_applicable_requirements: Dict[str, Requirement] = {}

        for res in results:
            if isinstance(res, Exception):
                final.warnings.append(f"En sub-agent feilet: {type(res).__name__}: {res}")
                continue
            if not isinstance(res, BaseAssessment):
                final.warnings.append(f"Mottok ukjent resultat-type: {type(res).__name__}")
                continue

            for rule in res.triggered_rules:
                all_triggered_rules[rule.rule_id] = rule 
            for req in res.applicable_requirements:
                all_applicable_requirements[req.code] = req

            final.information_gaps.extend(res.information_gaps)
            final.recommendations.extend(res.recommendations)
            final.warnings.extend(res.warnings)
            final.reasoning_steps.append(f"--- Begrunnelse fra {res.agent_name} ---")
            final.reasoning_steps.extend(res.reasoning_steps)

        final.triggered_rules = sorted(list(all_triggered_rules.values()), key=lambda r: r.rule_id)
        final.applicable_requirements = sorted(list(all_applicable_requirements.values()), key=lambda r: r.code)

        return final

    def _create_verification_failed_assessment(self, procurement: BaseProcurementInput, result: 'VerificationResult') -> BaseAssessment:
        """
        Lager et spesialisert BaseAssessment-objekt når leverandør-verifiseringen
        ikke kan fullføres automatisk.
        """
        assessment = BaseAssessment(
            procurement_id=procurement.procurement_id,
            procurement_name=procurement.name,
            agent_name="oslomodell_orchestrator",
            confidence_score=1.0,
        )
        
        assessment.reasoning_steps.append("Leverandør-verifisering ble utført som første steg.")
        
        if result.status == VerificationStatus.WARNING:
            assessment.warnings.append(result.message)
            if 'merknad' in result.metadata:
                assessment.warnings.append(f"Merknad fra OBS-liste: {result.metadata['merknad']}")
        
        elif result.status == VerificationStatus.ERROR:
            assessment.warnings.append(f"FEIL: {result.message}")
        
        elif result.status == VerificationStatus.NEEDS_SELECTION:
            assessment.recommendations.append(f"AVKLARING KREVES: {result.message}")
            options_text = [opt.get('display_text', opt.get('navn')) for opt in result.options]
            assessment.recommendations.extend(options_text)
            assessment.information_gaps.append("Entydig leverandør er ikke identifisert.")

        assessment.summary_prose = "Vurderingen ble stoppet fordi den spesifiserte leverandøren ikke kunne verifiseres automatisk. Se anbefalinger og advarsler for detaljer og neste steg."
        return assessment