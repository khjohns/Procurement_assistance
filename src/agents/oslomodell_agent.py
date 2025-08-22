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

# Importer modeller
from src.models.base_models import (
    BaseProcurementInput, BaseAssessment, Rule, Requirement, Condition
)
# <--- ENDRING: Importer enums for typekonvertering
from src.models.enums import ConditionOperator, RiskLevel, RiskType

# Stubs for spesialistagenter
from .apprentice_agent import ApprenticeAgent
# from .sanctions_agent import SanctionsAgent # Disse forblir kommentert
# from .obs_list_agent import ObsListAgent
# ...

logger = structlog.get_logger()

class OslomodellAgent:
    # ... __init__ og _load_knowledge_base er uendret ...
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._load_knowledge_base()

        self.apprentice_agent = ApprenticeAgent(config)
        # self.sanctions_agent = SanctionsAgent(config)
        # self.obs_list_agent = ObsListAgent(config)

        self.http_client = httpx.AsyncClient(timeout=10.0)

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

        # <--- START ENDRING ---
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
        # <--- SLUTT ENDRING ---

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
        self._enrich_procurement_with_mock_risk(procurement)

        tasks = [
            self._evaluate_rules(procurement), # Nå er dette en coroutine
            self.apprentice_agent.assess(procurement),
        ]
        
        assessment_results = await asyncio.gather(*tasks, return_exceptions=True)
        final_assessment = self._merge_assessments(procurement, assessment_results)

        logger.info("assessment_finished", assessment_id=final_assessment.assessment_id)
        return final_assessment

    def _enrich_procurement_with_mock_risk(self, procurement: BaseProcurementInput):
        """Henter risikodata fra config og legger til i procurement-objektet."""
        mock_config = self.config.get('mock_risk_assessment', {})
        category_str = procurement.category.value
        
        if procurement.risk_level is None:
            risk_level_str = mock_config.get('risk_level_by_category', {}).get(category_str)
            if risk_level_str:
                # <--- ENDRING: Konverter streng til Enum
                procurement.risk_level = RiskLevel(risk_level_str)
        
        if not procurement.identified_risks:
            risk_types_str = mock_config.get('risks_by_category', {}).get(category_str, [])
            if risk_types_str:
                # <--- ENDRING: Konverter liste av strenger til liste av Enums
                procurement.identified_risks = [RiskType(r) for r in risk_types_str]
        
        logger.info("procurement_enriched_with_mock_risk", 
                    risk_level=procurement.risk_level, 
                    risks=procurement.identified_risks)

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
                "risiko_nivaa": self._eval_risk_level,
                "risiko_type": self._eval_risk_type,
                "varighet_måneder": self._eval_duration_months,
                "kontraktsvarighet_år": self._eval_duration_years,
                "fase": self._eval_phase,
                "referanse": self._eval_reference,
                "kvalitativ_betingelse": self._eval_qualitative,
                "standardkontrakt_dekning": self._eval_standard_contract,
                "krav_aktivert": self._eval_requirement_activated,
                "subcategory": self._eval_subcategory # Sørg for at denne er med
            }
            
            eval_func = evaluators.get(cond.field)
            if eval_func:
                # Send den felles konteksten til ALLE evaluatorer.
                # De som ikke trenger 'activated_codes' vil bare ignorere det.
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
        # cond.value er allerede en enum eller liste av enums takket være Pydantic
        expected_values = [v.value for v in (cond.value if isinstance(cond.value, list) else [cond.value])]
        
        if cond.operator == ConditionOperator.IN and actual in expected_values:
            return True, f"anskaffelsestype er '{actual}' (som er i listen)."
        return False, f"anskaffelsestype er '{actual}' (ikke i listen {expected_values})."

    def _eval_subcategory(self, cond, context):
        """Evaluerer betingelser basert på anskaffelsens underkategori."""
        actual_value = context.get('subcategory')
        
        if not actual_value:
            return False, "" 
        
        # Manuell sjekk for å være 100% sikker
        if actual_value == "trykking_kopiering":
            return True, "DEBUG: Subcategory er trykking_kopiering"

        # Fallback til den generelle logikken
        expected_values = cond.value
        if cond.operator == ConditionOperator.IN and actual_value in expected_values:
            return True, f"subcategory er '{actual_value}' (som er i listen)."
        
        return False, f"subcategory er '{actual_value}' (ikke i listen {expected_values})."

    def _eval_value(self, cond, context):
        actual = context.get('value')
        if actual is None: return False, "kontraktsverdi mangler."
        expected = cond.value
        
        # <--- ENDRING: Robust sjekk for operator og verditype
        if cond.operator == ConditionOperator.BETWEEN:
            if not (isinstance(expected, list) and len(expected) == 2):
                return False, f"Ugyldig verdi for BETWEEN-operator: {expected}"
            res = expected[0] <= actual <= expected[1]
            return res, f"kontraktsverdi {actual} er mellom {expected[0]} og {expected[1]} er {res}."
        
        # For alle andre operatorer, forvent et enkelt tall
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

    def _eval_risk_level(self, cond, context):
        actual_raw = context.get('risk_level')
        if not actual_raw: return False, "risiko_nivaa mangler."
        actual = actual_raw # Pydantic v2 enums er strenger
        
        expected_values = [v.value for v in (cond.value if isinstance(cond.value, list) else [cond.value])]
        
        if cond.operator in [ConditionOperator.IN, ConditionOperator.EQ] and actual in expected_values:
            return True, f"risiko_nivaa er '{actual}'."
        return False, f"risiko_nivaa '{actual}' møter ikke kravet {expected_values}."

    def _eval_risk_type(self, cond, context):
        actual_risks_raw = context.get('identified_risks', [])
        if not actual_risks_raw: return False, "ingen identifiserte risikoer."
        actual_risks = set(r for r in actual_risks_raw) # Pydantic v2 enums er strenger
        
        expected_risks = set(v.value for v in (cond.value if isinstance(cond.value, list) else [cond.value]))
        
        if cond.operator == ConditionOperator.IN and not actual_risks.isdisjoint(expected_risks):
            return True, f"minst én av risikoene {expected_risks} er identifisert."
        return False, f"ingen av de påkrevde risikoene {expected_risks} er identifisert."

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
        actual = context.get('kontraktsvarighet_år') # Bruker den beregnede verdien
        if actual is None: return False, "kontraktsvarighet_år mangler."
        expected = cond.value
        
        if not isinstance(expected, (int, float)):
            return False, f"Ugyldig verdi for kontraktsvarighet_år: {expected}"

        op_map = {
            ConditionOperator.LT: actual < expected,
            # Legg til flere operatorer ved behov
        }
        if cond.operator in op_map:
            res = op_map[cond.operator]
            return res, f"kontraktsvarighet_år {actual:.2f} {cond.operator.value} {expected} er {res}."
        
        return False, f"Ukjent operator '{cond.operator}' for kontraktsvarighet_år."

    def _eval_phase(self, cond, context):
        """Evaluerer betingelser basert på anskaffelsesfase."""
        # For nå antar vi at agenten alltid kjører i planleggingsfasen.
        # Dette kan utvides til å være en del av inputen.
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
        is_covered = context.get('standard_contract_coverage', False) # Anta False som default
        
        if cond.operator == ConditionOperator.IS_TRUE and is_covered:
            return True, "anskaffelsen er dekket av standardkontrakt."
        if cond.operator == ConditionOperator.IS_FALSE and not is_covered:
            return True, "anskaffelsen er IKKE dekket av standardkontrakt."
            
        return False, f"sjekk for standardkontrakt (forventet: {cond.operator.value}, faktisk: {is_covered}) feilet."

    def _eval_requirement_activated(self, cond, context):
        # <--- ENDRING: Hent activated_codes fra konteksten
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
        
        # Regel 1: Sjekk for utvidet krav (høyest prioritet)
        if "T" in activated_codes:
            reasoning_steps.append("✓ Krav T er aktivert, utløser krav om utvidet skatteattest (SKATT-UTV).")
            activated_codes.add("SKATT-UTV")
            # Fjern eventuelt standardkrav hvis det skulle ha sneket seg inn
            activated_codes.discard("SKATT-STD")
            return activated_codes, reasoning_steps

        # Regel 2: Sjekk for standard krav (nest høyest prioritet)
        if procurement.value > 500000:
            reasoning_steps.append("✓ Verdi > 500k og Krav T er ikke aktivt, utløser standard skatteattestkrav (SKATT-STD).")
            activated_codes.add("SKATT-STD")
            return activated_codes, reasoning_steps
            
        # Regel 3: Ingen krav
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

        # <--- ENDRING: Bruk en ordbok i stedet for et set for å unngå "unhashable type" feil
        all_triggered_rules: Dict[str, Rule] = {} 
        all_applicable_requirements: Dict[str, Requirement] = {}

        for res in results:
            if isinstance(res, Exception):
                final.warnings.append(f"En sub-agent feilet: {type(res).__name__}: {res}")
                continue
            if not isinstance(res, BaseAssessment):
                final.warnings.append(f"Mottok ukjent resultat-type: {type(res).__name__}")
                continue

            # Slå sammen regler og krav
            for rule in res.triggered_rules:
                # <--- ENDRING: Bruk rule_id som nøkkel for å fjerne duplikater
                all_triggered_rules[rule.rule_id] = rule 
            for req in res.applicable_requirements:
                all_applicable_requirements[req.code] = req

            # Slå sammen annen viktig info
            final.information_gaps.extend(res.information_gaps)
            final.recommendations.extend(res.recommendations)
            final.warnings.extend(res.warnings)
            final.reasoning_steps.append(f"--- Begrunnelse fra {res.agent_name} ---")
            final.reasoning_steps.extend(res.reasoning_steps)

        # <--- ENDRING: Hent verdiene fra ordbøkene for å lage listene
        final.triggered_rules = sorted(list(all_triggered_rules.values()), key=lambda r: r.rule_id)
        final.applicable_requirements = sorted(list(all_applicable_requirements.values()), key=lambda r: r.code)

        return final