# src/agents/obs_list_agent.py
import csv
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
import structlog
import unicodedata

from ..services.brreg_service import BrregService

logger = structlog.get_logger()

class VerificationStatus(str, Enum):
    OK = "OK"
    WARNING = "ADVARSEL"
    ERROR = "FEIL"
    NEEDS_SELECTION = "FLERE TREFF"

class VerificationResult(BaseModel):
    status: VerificationStatus
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    options: List[Dict[str, Any]] = Field(default_factory=list)

class ObsListAgent:
    def __init__(self, brreg_service: BrregService, obs_list_path: str, config: Dict[str, Any]):
        self.brreg_service = brreg_service
        self.obs_list = self._load_obs_list(obs_list_path)
        # --- NYTT: Hent konfigurasjonen for auto-valg ---
        self.config = config.get('supplier_verification_config', {})
        self.auto_select_first = self.config.get('auto_select_first_match', False)
        logger.info("ObsListAgent initialized", auto_select_first=self.auto_select_first)

    def _load_obs_list(self, path: str) -> Dict[str, Dict[str, str]]:
        # ... (denne metoden er uendret) ...
        log = logger.bind(file_path=path)
        log.info("loading_obs_list")
        obs_data = {}
        try:
            with open(path, mode='r', encoding='utf-8-sig') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    org_nr = row.get('Organisasjonsnummer', '').strip()
                    if org_nr.isdigit() and len(org_nr) == 9:
                        obs_data[org_nr] = {
                            "navn": row.get('Navn', ''),
                            "merknad": row.get('Merknad', '')
                        }
                    else:
                        log.warning("invalid_org_nr_in_obs_list_skipped", raw_value=org_nr)
            log.info("obs_list_loaded_successfully", count=len(obs_data))
            return obs_data
        except FileNotFoundError:
            log.error("obs_list_file_not_found")
            raise
        except Exception as e:
            log.error("failed_to_load_obs_list", error=str(e))
            raise

    def _normalize_name(self, name: str) -> str:
        # ... (denne metoden er uendret) ...
        name = name.lower()
        name = name.replace(" as", "").replace(" asa", "").strip()
        name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
        return name

    async def verify_supplier(self, supplier_name: str, is_foreign: bool) -> VerificationResult:
        if is_foreign:
            return VerificationResult(
                status=VerificationStatus.WARNING,
                message="Utenlandske leverandører kan ikke verifiseres automatisk mot norske registre."
            )

        logger.info("obs_agent_normalizing_supplier_name", supplier_name=supplier_name)
        search_name = self._normalize_name(supplier_name)
        
        try:
            companies = await self.brreg_service.find_company(search_name)
            
            if not companies:
                return VerificationResult(status=VerificationStatus.ERROR, message=f"Ingen treff for '{supplier_name}' i Brønnøysundregistrene.")

            # --- NYTT: Logikk for auto-valg ---
            if len(companies) > 1 and self.auto_select_first:
                logger.info("multiple_brreg_hits_auto_selecting_first", count=len(companies), selected_name=companies[0].get('navn'))
                # Lag en advarsel, men fortsett med det første treffet
                selected_company = companies[0]
                org_nr = selected_company.get('orgnr')
                
                # Sjekk det valgte selskapet mot OBS-listen
                if org_nr in self.obs_list:
                    obs_entry = self.obs_list[org_nr]
                    return VerificationResult(
                        status=VerificationStatus.WARNING,
                        message=f"Leverandøren '{selected_company.get('navn')}' ({org_nr}) ble funnet på OBS-listen.",
                        metadata={"organisasjonsnummer": org_nr, "merknad": obs_entry.get('merknad')}
                    )
                
                return VerificationResult(
                    status=VerificationStatus.OK,
                    message=f"Valgte automatisk første treff for '{supplier_name}': '{selected_company.get('navn')}' ({org_nr}).",
                    metadata={"organisasjonsnummer": org_nr, "navn": selected_company.get('navn')}
                )
            # --- SLUTT NY LOGIKK ---

            if len(companies) > 1:
                return VerificationResult(
                    status=VerificationStatus.NEEDS_SELECTION,
                    message=f"Flere mulige treff for '{supplier_name}'. Vennligst velg riktig leverandør.",
                    options=companies
                )

            # Entydig treff
            company = companies[0]
            org_nr = company.get('orgnr')
            
            if org_nr in self.obs_list:
                obs_entry = self.obs_list[org_nr]
                return VerificationResult(
                    status=VerificationStatus.WARNING,
                    message=f"Leverandøren '{company.get('navn')}' ({org_nr}) ble funnet på OBS-listen.",
                    metadata={"organisasjonsnummer": org_nr, "merknad": obs_entry.get('merknad')}
                )

            return VerificationResult(
                status=VerificationStatus.OK,
                message=f"Leverandør '{company.get('navn')}' ({org_nr}) verifisert og ikke funnet på OBS-listen.",
                metadata={"organisasjonsnummer": org_nr, "navn": selected_company.get('navn')}
            )
        except Exception as e:
            logger.error("brreg_search_failed", error=str(e))
            return VerificationResult(status=VerificationStatus.ERROR, message=f"Søk mot Brønnøysund feilet: {e}")