# src/agents/apprentice_agent.py
import csv
import json
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path

import structlog

from src.models.base_models import (
    BaseProcurementInput, BaseAssessment, Requirement
)

logger = structlog.get_logger()

class ApprenticeAgent:
    """
    Spesialist-agent for å vurdere om det skal stilles krav om lærlinger.
    ... (docstring uendret) ...
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialiserer agenten med sin spesifikke konfigurasjon.
        """
        self.config = config.get('apprentice_agent_config', {})
        if not self.config:
            raise ValueError("Konfigurasjon for 'apprentice_agent_config' mangler.")
        
        # Laster data for både hovedprogramområder og spesifikke fag
        self.udir_data_main_programs = self._load_udir_data(main_programs_only=True)
        self.udir_data_specific_trades = self._load_udir_data(main_programs_only=False) # Kan aktiveres for dypere analyse
        
        kb_path = config.get('knowledge_base', {}).get('file_path')
        self.requirement_v_template: Optional[Requirement] = self._load_requirement_template(kb_path, "V")
        
        if not self.requirement_v_template:
            logger.warning("Krav-definisjon 'V' (lærlinger) ikke funnet i kunnskapsbasen. Agenten vil ikke kunne aktivere kravet.")

    def _load_udir_data(self, main_programs_only: bool = True) -> Dict[str, float]:
        """
        Laster og parser UDIR-data direkte fra den offisielle CSV-filen.
        Håndterer semikolon-separator, komma-desimaler og filtrering.
        
        Args:
            main_programs_only: Hvis True, lastes kun data for hovedprogramområder (Nivå 2).
                                Hvis False, lastes data for spesifikke fag (Nivå 3).
        """
        data_file_path = self.config.get('udir_data_file')
        if not data_file_path:
            raise ValueError("Sti til UDIR-datafil mangler i konfigurasjonen.")
        
        udir_data = {}
        log = logger.bind(file_path=data_file_path, filter_main_programs=main_programs_only)
        log.info("loading_udir_data_from_source_file")
        
        target_level = '2' if main_programs_only else '3'

        try:
            with open(data_file_path, mode='r', encoding='utf-8-sig') as infile: # 'utf-8-sig' for å håndtere BOM
                # Bruker DictReader for robust kolonne-tilgang via header-navn
                reader = csv.DictReader(infile, delimiter=';')
                
                for row in reader:
                    try:
                        level = row.get('ProgramomraadeNivaa')
                        # Siste kolonne har et langt og variabelt navn, så vi henter den dynamisk
                        percentage_col_name = list(row.keys())[-1]
                        percentage_str = row.get(percentage_col_name, '').strip()
                        
                        # Filtrer på nivå
                        if level != target_level:
                            continue

                        # Hent navnet basert på nivå
                        name_key = 'UtdanningsprogramvariantNavn' if main_programs_only else 'ProgramomraadeNavn'
                        trade_name = row.get(name_key, '').strip()

                        if not trade_name or not percentage_str:
                            continue # Hopp over rader med manglende data

                        # Konverter prosent til float (håndterer komma-desimal)
                        percentage = float(percentage_str.replace(',', '.')) / 100.0
                        udir_data[trade_name] = percentage

                    except (ValueError, IndexError, KeyError) as e:
                        log.warning("invalid_data_row_skipped", row=row, error=str(e))

            log.info("udir_data_loaded_successfully", trade_count=len(udir_data))
            return udir_data
        except FileNotFoundError:
            log.error("udir_data_file_not_found")
            raise
        except Exception as e:
            log.error("failed_to_load_udir_data", error=str(e))
            raise

    # _load_requirement_template er uendret.
    def _load_requirement_template(self, kb_path: str, code: str) -> Optional[Requirement]:
        """Laster en spesifikk krav-mal fra hoved-kunnskapsbasen."""
        if not kb_path:
            return None
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                kb = json.load(f)
                reqs = kb[0].get('document_metadata', {}).get('document_level_requirements', [])
                for req_dict in reqs:
                    if req_dict.get('code') == code:
                        return Requirement.model_validate(req_dict)
        except Exception:
            return None
        return None

    # assess-metoden er uendret.
    async def assess(self, procurement: BaseProcurementInput) -> BaseAssessment:
        """Kjører hele vurderingsprosessen for lærlingekrav."""
        assessment = BaseAssessment(
            procurement_id=procurement.procurement_id,
            procurement_name=procurement.name,
            agent_name="apprentice_agent",
            confidence_score=1.0, # Start optimistisk
        )
        
        log = logger.bind(procurement_id=procurement.procurement_id)
        log.info("apprentice_assessment_started")

        # Steg 1: Deterministisk sjekk av terskelverdier
        log.info("step_1_checking_thresholds")
        if procurement.value < self.config['threshold_value']:
            reason = f"Anskaffelsens verdi ({procurement.value:,} NOK) er under terskelverdien ({self.config['threshold_value']:,} NOK)."
            log.info("threshold_not_met_value", value=procurement.value)
            assessment.reasoning_steps.append(reason)
            return assessment

        if procurement.duration_months < self.config['min_duration_months']:
            reason = f"Varigheten ({procurement.duration_months} mnd) er under minimumskravet ({self.config['min_duration_months']} mnd)."
            log.info("threshold_not_met_duration", duration=procurement.duration_months)
            assessment.reasoning_steps.append(reason)
            return assessment

        assessment.reasoning_steps.append("Terskelverdier for verdi og varighet er møtt.")
        
        # Steg 2 & 3 kombinert: Identifiser spesifikke fag og sjekk behov
        log.info("step_2_3_identifying_trades_and_checking_need")
        relevant_trades_with_need = self._find_relevant_trades_with_special_need(procurement.description)

        if not relevant_trades_with_need:
            reason = "Ingen spesifikke, relevante fagområder med et dokumentert 'særlig behov' ble identifisert."
            log.info("no_specific_trades_with_special_need_found")
            assessment.reasoning_steps.append(reason)
            return assessment

        assessment.reasoning_steps.append(f"Fagområder med 'særlig behov' funnet: {', '.join(relevant_trades_with_need)}.")

        # Steg 4: Vurder uforholdsmessighet (plassholder)
        log.info("step_4_checking_proportionality")
        is_disproportionate, reason = self._check_proportionality(procurement.description)

        if is_disproportionate:
            log.warning("proportionality_check_failed", reason=reason)
            assessment.reasoning_steps.append(f"Kravet anses som uforholdsmessig: {reason}")
            # VIKTIG: Vi nullstiller kravene fordi dette er en unntaksregel
            assessment.applicable_requirements = []
            assessment.recommendations = ["Det anbefales IKKE å stille krav om lærlinger på grunn av uforholdsmessighet."]
            return assessment

        # Konklusjon
        log.info("assessment_successful_requirement_applies")
        if self.requirement_v_template:
            assessment.applicable_requirements.append(self.requirement_v_template)
            assessment.recommendations.append("Det anbefales å stille krav om lærlinger (Krav V) i denne anskaffelsen.")
        else:
            assessment.warnings.append("Lærlingekrav gjelder, men krav-mal 'V' kunne ikke lastes fra kunnskapsbasen.")

        return assessment

    def _check_proportionality(self, description: str) -> (bool, str):
        """
        Sjekker for åpenbare tegn på at et lærlingekrav vil være uforholdsmessig.
        Dette er en deterministisk sjekk for "red flag"-nøkkelord.
        Kan utvides med LLM for mer avansert forståelse.
        """
        lower_desc = description.lower()
        
        red_flags = {
            "akutt": "Anskaffelsen er beskrevet som et akutt hasteoppdrag.",
            "hasteoppdrag": "Anskaffelsen er beskrevet som et akutt hasteoppdrag.",
            "særlig sårbare brukere": "Arbeidet innebærer direkte kontakt med sårbare grupper.",
            "høysikkerhet": "Arbeidet krever spesielle sikkerhetsklareringer som kan være vanskelig for lærlinger.",
            "ekstremt kortvarig": "Oppdraget er beskrevet som ekstremt kortvarig."
        }

        for flag, reason in red_flags.items():
            if flag in lower_desc:
                return True, reason
                
        return False, ""

    def _find_relevant_trades_with_special_need(self, description: str) -> List[str]:
        """
        Identifiserer spesifikke fag fra beskrivelsen og sjekker om noen av dem
        har et "særlig behov" for lærlinger.
        """
        found_trades_with_need = set()
        lower_desc = description.lower()

        # Nøkkelord-mapping til offisielle UDIR-fagnavn (Nivå 3)
        # Dette er mer detaljert enn før.
        keyword_map = {
            "rørlegger": "BARLF3 - Rørleggerfaget",
            "tømrer": "BATMF3 - Tømrerfaget",
            "snekker": "BASNE3 - Snekkerfaget",
            "elektriker": "ELELE3 - Elektrikerfaget",
            "maler": "BAMOT3 - Maler- og overflateteknikkfaget",
            "renhold": "BAROF3 - Renholdsoperatørfaget",
            "dataelektroniker": "ELDAT3 - Dataelektronikerfaget",
            "it-utvikler": "IMIUV3 - IT-utviklerfaget",
            "it-drift": "IMITD3 - IT-driftsfaget",
            "kokk": "RMKOK3 - Kokkfaget",
            "servitør": "RMSER3 - Servitørfaget"
            # ... legg til flere mappings etter behov ...
        }

        for keyword, trade_name in keyword_map.items():
            if keyword in lower_desc:
                # Sjekk om dette faget har et særlig behov
                if trade_name in self.udir_data_specific_trades:
                    andel = self.udir_data_specific_trades[trade_name]
                    if andel < self.config['special_need_threshold']:
                        found_trades_with_need.add(trade_name)
        
        return list(found_trades_with_need)

    def _identify_main_programs_from_description(self, description: str) -> List[str]:
        """
        Simulert/enkel funksjon for å identifisere hovedprogramområder.
        Matcher nøkkelord mot de offisielle navnene fra UDIR-data.
        """
        found_programs = set()
        # Nøkkelord-mapping til offisielle UDIR-programnavn (Nivå 2)
        keyword_map = {
            # Bygg og anlegg
            "bygg": "Bygg- og anleggsteknikk", "anlegg": "Bygg- og anleggsteknikk",
            "rørlegger": "Bygg- og anleggsteknikk", "tømrer": "Bygg- og anleggsteknikk",
            "snekker": "Bygg- og anleggsteknikk", "murer": "Bygg- og anleggsteknikk",
            "maler": "Bygg- og anleggsteknikk", "graving": "Bygg- og anleggsteknikk",
            # Elektro
            "elektro": "Elektro og datateknologi", "elektriker": "Elektro og datateknologi",
            "data": "Elektro og datateknologi", "automasjon": "Elektro og datateknologi",
            # IT
            "it": "Informasjonsteknologi og medieproduksjon", "ikt": "Informasjonsteknologi og medieproduksjon",
            "utvikling": "Informasjonsteknologi og medieproduksjon", "programmering": "Informasjonsteknologi og medieproduksjon",
            # Restaurant og matfag
            "mat": "Restaurant- og matfag", "kantine": "Restaurant- og matfag",
            "kokk": "Restaurant- og matfag", "baker": "Restaurant- og matfag",
            # Salg og service
            "renhold": "Salg, service og reiseliv", # NB: Renholdsoperatørfaget ligger under Bygg/anlegg i filen, men la oss teste en annen kobling. Bør verifiseres.
            "service": "Salg, service og reiseliv", "sikkerhet": "Salg, service og reiseliv", 
            "vekter": "Salg, service og reiseliv",
            # Helse
            "helse": "Helse- og oppvekstfag", "ambulanse": "Helse- og oppvekstfag",
            # Teknologi og industri
            "industri": "Teknologi- og industrifag", "mekaniker": "Teknologi- og industrifag",
            "sveise": "Teknologi- og industrifag", "logistikk": "Teknologi- og industrifag"
        }
        
        lower_desc = description.lower()
        for keyword, program in keyword_map.items():
            if keyword in lower_desc:
                # Sjekk at programmet faktisk finnes i våre data
                if program in self.udir_data_main_programs:
                    found_programs.add(program)
        
        return list(found_programs)