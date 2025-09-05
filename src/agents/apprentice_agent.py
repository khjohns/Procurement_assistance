# src/agents/apprentice_agent.py
import csv
import json
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path

from pydantic import BaseModel, Field

import structlog

from src.models.base_models import (
    BaseProcurementInput, BaseAssessment, Requirement
)

from src.services.llm_gateway import LLMGateway, LLMStructuredResponseError


logger = structlog.get_logger()

class RelevantTradesResponse(BaseModel):
    relevante_fagomraader: List[str] = Field(
        ...,
        description="En liste med de nøyaktige navnene på relevante fagområder fra den oppgitte listen."
    )

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
        
        self.udir_data_main_programs = self._load_udir_data(main_programs_only=True)
        self.udir_data_specific_trades = self._load_udir_data(main_programs_only=False)
        
        kb_path = config.get('knowledge_base', {}).get('file_path')
        self.requirement_v_template: Optional[Requirement] = self._load_requirement_template(kb_path, "V")
        
        if not self.requirement_v_template:
            logger.warning("Krav-definisjon 'V' (lærlinger) ikke funnet i kunnskapsbasen.")

        self.llm_gateway: Optional[LLMGateway] = None
        self.llm_config = self.config.get('llm', {})
        
        if self.llm_config.get('enabled'):
            try:
                # --- KORREKSJON: Kallet til LLMGateway() er nå gyldig ---
                self.llm_gateway = LLMGateway()
                
                self.extract_trades_prompt = self.llm_config.get('prompt_extract_trades', '')
                
                if not self.extract_trades_prompt:
                    logger.warning("prompt_extract_trades not found in config, LLM extraction may fail")
                
                logger.info("ApprenticeAgent: LLMGateway enabled and initialized.")
            except Exception as e:
                logger.error("Failed to initialize LLMGateway", error=str(e))
                self.llm_gateway = None
                self.extract_trades_prompt = ''
        else:
            self.extract_trades_prompt = ''
            logger.info("ApprenticeAgent: LLM disabled, using keyword-based trade detection")

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

    def create_assessment_from_llm_result(self, procurement: BaseProcurementInput, relevant_trades: List[str]) -> Optional[BaseAssessment]:
        """
        Bygger et fullverdig BaseAssessment-objekt basert på en liste med
        identifiserte fagområder fra en LLM.
        """
        assessment = BaseAssessment(
            procurement_id=procurement.procurement_id,
            procurement_name=procurement.name,
            agent_name="apprentice_agent",
            confidence_score=0.95, # Litt lavere siden den er LLM-basert
        )
        log = logger.bind(procurement_id=procurement.procurement_id)
        
        assessment.reasoning_steps.append(f"LLM identifiserte relevante fagområder: {', '.join(relevant_trades)}.")

        # Steg 3: Sjekk for "særlig behov" (logikk gjenbrukt)
        trades_with_special_need = self._get_trades_with_special_need(relevant_trades)
        if not trades_with_special_need:
            assessment.reasoning_steps.append("Ingen av fagene har 'særlig behov'. Krav utløses ikke.")
            return assessment # Returnerer et assessment uten krav

        assessment.reasoning_steps.append(f"Fagområder med 'særlig behov': {', '.join(trades_with_special_need)}.")

        # Steg 4: Vurder uforholdsmessighet (logikk gjenbrukt)
        is_disproportionate, reason = self._check_proportionality(procurement.description)
        if is_disproportionate:
            assessment.reasoning_steps.append(f"Kravet anses uforholdsmessig: {reason}")
            return assessment

        # Konklusjon: Alle sjekker bestått
        if self.requirement_v_template:
            assessment.applicable_requirements.append(self.requirement_v_template)
            assessment.recommendations.append("Det anbefales å stille krav om lærlinger (Krav V).")
        
        return assessment
    

    def _get_trades_with_special_need(self, trades: List[str]) -> List[str]:
        """Gitt en liste med fag, returner de som har et 'særlig behov'."""
        trades_with_need = []
        # Gå gjennom de rene fagnavnene fra LLM
        for llm_trade_name in trades:
            # Gå gjennom de fulle fagnavnene (med kode) fra UDIR-dataen
            for udir_full_name, andel in self.udir_data_specific_trades.items():
                # Sjekk om det rene navnet finnes i det fulle navnet OG om andelen er under terskelen
                if llm_trade_name in udir_full_name and andel < self.config['special_need_threshold']:
                    # Legg til det FULLE navnet for konsistens
                    trades_with_need.append(udir_full_name)
                    # Gå til neste LLM-fag for å unngå duplikater hvis flere treff
                    break 
        return list(set(trades_with_need)) # Bruk set() for å sikre unike verdier

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

    def _find_relevant_trades_with_keywords(self, description: str) -> List[str]:
        """
        Fallback-metode som bruker en enkel nøkkelord-mapping.
        """
        found_trades = set()
        lower_desc = description.lower()

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
            if keyword in lower_desc and trade_name in self.udir_data_specific_trades:
                found_trades.add(trade_name)
        
        return list(found_trades)