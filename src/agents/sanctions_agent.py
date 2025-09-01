# src/agents/sanctions_agent.py
import csv
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List, Tuple
import structlog
import httpx
import os
import time
from datetime import timedelta

# Importer gjenbrukbare komponenter
from .obs_list_agent import VerificationResult, VerificationStatus
from ..services.brreg_service import BrregService

# Importer fuzzy matching-biblioteket
from thefuzz import fuzz

logger = structlog.get_logger()

class SanctionsAgent:
    """
    En deterministisk agent for å verifisere leverandører og deres reelle
    rettighetshavere mot EUs konsoliderte sanksjonsliste.
    """
    def __init__(self, http_client: httpx.AsyncClient, brreg_service: BrregService, 
                 sanctions_url: str, cache_path: str, cache_ttl_hours: int = 24, fuzzy_threshold: int = 85):
        self.http_client = http_client
        self.brreg_service = brreg_service
        self.sanctions_url = sanctions_url
        self.cache_path = cache_path
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.fuzzy_threshold = fuzzy_threshold
        self._sanctions_list: Optional[List[Dict[str, str]]] = None

    def _normalize_name(self, name: str) -> str:
        """Normaliserer et navn for å forbedre matching."""
        if not name:
            return ""
        # Konverter til store bokstaver
        normalized = name.upper()
        # Fjern vanlige forretningssuffikser (kan utvides)
        suffixes = [" AS", " ASA", " LTD", " AB", " GMBH", " INC", ","]
        for suffix in suffixes:
            normalized = normalized.replace(suffix, "")
        # Fjern tegnsetting
        normalized = ''.join(filter(str.isalnum, normalized))
        return normalized

    async def _get_sanctions_list(self) -> List[Dict[str, str]]:
        """
        Henter sanksjonslisten fra cache eller nett, parser den, og returnerer en
        prosessert liste klar for søk. Listen bufres i minnet etter første gangs lasting.
        """
        if self._sanctions_list is not None:
            return self._sanctions_list

        log = logger.bind(cache_path=self.cache_path, url=self.sanctions_url)
        xml_content = None
        use_cache = False

        # Sjekk om cache-filen er gyldig
        if os.path.exists(self.cache_path):
            file_mod_time = os.path.getmtime(self.cache_path)
            if (time.time() - file_mod_time) < self.cache_ttl.total_seconds():
                log.info("using_fresh_sanctions_cache")
                use_cache = True
            else:
                log.info("sanctions_cache_is_stale")

        if use_cache:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        else:
            log.info("downloading_fresh_sanctions_list")
            try:
                response = await self.http_client.get(self.sanctions_url, timeout=60.0)
                response.raise_for_status()
                xml_content = response.text
                # Lagre den nye filen til cache
                with open(self.cache_path, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                log.info("sanctions_list_downloaded_and_cached")
            except httpx.HTTPError as e:
                log.error("failed_to_download_sanctions_list", error=str(e))
                # Hvis nedlasting feiler, prøv å bruke utdatert cache som fallback
                if os.path.exists(self.cache_path):
                    log.warning("using_stale_cache_as_fallback")
                    with open(self.cache_path, 'r', encoding='utf-8') as f:
                        xml_content = f.read()
                else:
                    return [] # Kan ikke fortsette uten data

        # Parse XML og normaliser navn
        processed_list = []
        if xml_content:
            root = ET.fromstring(xml_content)
            # Namespace kan variere, finn den dynamisk
            namespace = {'ns': root.tag.split('}')[0][1:]}
            for entity in root.findall('ns:SANCTION_ENTITY', namespace):
                for name_alias in entity.findall('.//ns:NAME_ALIAS', namespace):
                    original_name = name_alias.get('WHOLE_NAME')
                    if original_name:
                        processed_list.append({
                            "original_name": original_name,
                            "normalized_name": self._normalize_name(original_name)
                        })
        
        self._sanctions_list = processed_list
        log.info("sanctions_list_parsed_and_loaded", count=len(self._sanctions_list))
        return self._sanctions_list

    def _check_names(self, names_to_check: List[str], sanctions_list: List[Dict[str, str]]) -> Tuple[List[Dict], List[Dict]]:
        """Sjekker en liste med navn mot sanksjonslisten for eksakte og fuzzy treff."""
        exact_matches = []
        fuzzy_matches = []

        for name in names_to_check:
            normalized_name_to_check = self._normalize_name(name)
            if not normalized_name_to_check:
                continue

            found_exact = False
            for sanction_entry in sanctions_list:
                # 1. Eksakt sjekk
                if normalized_name_to_check == sanction_entry["normalized_name"]:
                    exact_matches.append({
                        "name_checked": name,
                        "sanctioned_name": sanction_entry["original_name"]
                    })
                    found_exact = True
                    break # Gå til neste navn å sjekke
            
            if not found_exact:
                # 2. Fuzzy sjekk
                for sanction_entry in sanctions_list:
                    score = fuzz.ratio(normalized_name_to_check, sanction_entry["normalized_name"])
                    if score >= self.fuzzy_threshold:
                        fuzzy_matches.append({
                            "name_checked": name,
                            "sanctioned_name": sanction_entry["original_name"],
                            "score": score
                        })
        
        return exact_matches, fuzzy_matches

    async def check_sanctions(self, org_nr: str) -> VerificationResult:
        """
        Offentlig metode for å kjøre en full sanksjonskontroll for et gitt org.nr.
        """
        log = logger.bind(orgnr=org_nr)
        log.info("starting_sanctions_check")

        # Steg 1: Hent sanksjonslisten (fra cache/nett)
        sanctions_list = await self._get_sanctions_list()
        if not sanctions_list:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message="Kunne ikke laste sanksjonslisten. Kan ikke fullføre kontroll."
            )

        # Steg 2: Hent firmanavn og reelle rettighetshavere fra Brreg
        company_details = await self.brreg_service.get_company_details(org_nr)
        signature_info = await self.brreg_service.get_signature_info(org_nr)

        if not company_details or not signature_info:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Kunne ikke hente fullstendig informasjon for org.nr {org_nr} fra Brreg."
            )

        names_to_check = [company_details.get("navn", "")]
        for role_group in signature_info.roller.values():
            names_to_check.extend(role_group)
        
        log.info("names_to_check_compiled", names=names_to_check)

        # Steg 3: Utfør sjekken
        exact_matches, fuzzy_matches = self._check_names(names_to_check, sanctions_list)

        # Steg 4: Rapporter resultat
        if exact_matches:
            return VerificationResult(
                status=VerificationStatus.WARNING,
                message="ADVARSEL: EKSAKT TREFF FUNNET I SANKSJONSLISTEN!",
                metadata={"matches": exact_matches, "type": "Eksakt"}
            )
        
        if fuzzy_matches:
            return VerificationResult(
                status=VerificationStatus.WARNING,
                message="OBS: POTENSIELT TREFF FUNNET I SANKSJONSLISTEN (FUZZY MATCH)!",
                metadata={"matches": fuzzy_matches, "type": "Potensielt"}
            )

        return VerificationResult(
            status=VerificationStatus.OK,
            message=f"Ingen treff for '{company_details['navn']}' eller dets reelle rettighetshavere ble funnet i sanksjonsdatabasen."
        )