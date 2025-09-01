# src/services/brreg_service.py
"""
En komplett og robust tjeneste for å hente data fra flere av
Brønnøysundregistrenes API-er.
"""
from typing import Dict, Any, List, Optional
import httpx
import asyncio
from datetime import datetime
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# --- Pydantic-modeller for strukturert data ---
class BrregCompanyDetails(BaseModel):
    organisasjonsnummer: str
    navn: str
    organisasjonsform: Dict[str, Any] = Field(default_factory=dict)
    antallAnsatte: Optional[int] = None
    konkurs: bool = False
    underAvvikling: bool = False
    underTvangsavviklingEllerTvangsopplosning: bool = False

class BrregFullmakt(BaseModel):
    beskrivelse: str

class BrregSignatureInfo(BaseModel):
    signatur: Optional[BrregFullmakt] = None
    prokura: Optional[BrregFullmakt] = None
    roller: Dict[str, List[str]] = Field(default_factory=dict)

class ComprehensiveCompanyInfo(BaseModel):
    details: Optional[BrregCompanyDetails] = None
    signature: Optional[BrregSignatureInfo] = None
    financials: Optional[Dict[str, Any]] = None

class BrregService:
    def __init__(self, http_client: httpx.AsyncClient, enhetsregisteret_url: str, regnskapsregisteret_url: str, fullmakt_api_url: str):
        self.client = http_client
        self.enhetsregisteret_url = enhetsregisteret_url.rstrip('/')
        self.regnskapsregisteret_url = regnskapsregisteret_url.rstrip('/')
        self.fullmakt_api_url = fullmakt_api_url.rstrip('/')

    async def find_company(self, name: str, size: int = 5, include_details: bool = False) -> List[Dict[str, Any]]:
        """Søker etter et firma og inkluderer valgfrie detaljer."""
        log = logger.bind(search_name=name); log.info("brreg_service.find_company.start")
        if not name or len(name.strip()) < 2:
            log.warning("brreg_service.find_company.name_too_short"); return []
        
        try:
            url = f"{self.enhetsregisteret_url}/enheter"
            params = {"navn": name.strip(), "size": size}
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for enhet in data.get('_embedded', {}).get('enheter', []):
                result = {"navn": enhet.get('navn', ''), "orgnr": enhet.get('organisasjonsnummer', '')}
                if include_details:
                    result.update({
                        "organisasjonsform": enhet.get('organisasjonsform', {}).get('beskrivelse', ''),
                        "poststed": enhet.get('forretningsadresse', {}).get('poststed', ''),
                        "konkurs": enhet.get('konkurs', False),
                        "underAvvikling": enhet.get('underAvvikling', False)
                    })
                results.append(result)
            
            log.info("brreg_service.find_company.success", count=len(results))
            return results
        except httpx.HTTPError as e:
            log.error("brreg_service.find_company.http_error", error=str(e)); return []

    async def get_company_details(self, orgnr: str) -> Optional[BrregCompanyDetails]:
        log = logger.bind(orgnr=orgnr); log.info("brreg_service.get_company_details.start")
        if not orgnr or not orgnr.isdigit() or len(orgnr) != 9:
            log.warning("brreg_service.get_company_details.invalid_orgnr"); return None
        try:
            url = f"{self.enhetsregisteret_url}/enheter/{orgnr}"
            response = await self.client.get(url)
            if response.status_code in [404, 410]:
                log.warning(f"brreg_service.get_company_details.not_found_or_deleted"); return None
            response.raise_for_status()
            return BrregCompanyDetails(**response.json())
        except httpx.HTTPError as e:
            log.error("brreg_service.get_company_details.http_error", error=str(e)); return None

    async def _fetch_fullmakt_rule(self, orgnr: str, fullmakt_type: str) -> Optional[BrregFullmakt]:
        log = logger.bind(orgnr=orgnr, type=fullmakt_type)
        try:
            url = f"{self.fullmakt_api_url}/enheter/{orgnr}/{fullmakt_type}"
            response = await self.client.get(url)
            if response.status_code != 200: return None
            data = response.json()
            if "signeringsKombinasjon" in data and data["signeringsKombinasjon"]["kombinasjon"]:
                rule_text = data["signeringsKombinasjon"]["kombinasjon"][0].get("tekstforklaring")
                if rule_text: return BrregFullmakt(beskrivelse=rule_text)
            return None
        except httpx.HTTPError as e:
            log.error("brreg_service._fetch_fullmakt_rule.http_error", error=str(e)); return None

    async def get_signature_info(self, orgnr: str) -> Optional[BrregSignatureInfo]:
        log = logger.bind(orgnr=orgnr); log.info("brreg_service.get_signature_info.start")
        signatur_regel_task = self._fetch_fullmakt_rule(orgnr, "signatur")
        prokura_regel_task = self._fetch_fullmakt_rule(orgnr, "prokura")
        try:
            url = f"{self.enhetsregisteret_url}/enheter/{orgnr}/roller"
            response = await self.client.get(url)
            response.raise_for_status()
            roller_data = response.json()
            roller: Dict[str, List[str]] = {}
            for gruppe in roller_data.get('rollegrupper', []):
                for rolle_data in gruppe.get('roller', []):
                    try:
                        rolle_type = rolle_data['type']['beskrivelse']
                        person_navn = f"{rolle_data['person']['navn']['fornavn']} {rolle_data['person']['navn']['etternavn']}"
                        if rolle_type not in roller: roller[rolle_type] = []
                        roller[rolle_type].append(person_navn)
                    except KeyError: continue
        except httpx.HTTPError as e:
            log.error("brreg_service.get_signature_info.roles_http_error", error=str(e)); return None
        signatur_regel, prokura_regel = await asyncio.gather(signatur_regel_task, prokura_regel_task)
        return BrregSignatureInfo(signatur=signatur_regel, prokura=prokura_regel, roller=roller)

    async def _fetch_financials_for_year(self, orgnr: str, year: int) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.regnskapsregisteret_url}/regnskap/{orgnr}"; params = {"år": year}; 
            response = await self.client.get(url, params=params, follow_redirects=True)
            if response.status_code == 404: return None
            response.raise_for_status(); data = response.json()
            return data[0] if isinstance(data, list) and data else None
        except httpx.HTTPError as e:
            log.error("brreg_service._fetch_financials_for_year.http_error", error=str(e)); return None

    async def get_latest_available_financials(self, orgnr: str) -> Optional[Dict[str, Any]]:
        current_year = datetime.now().year
        for year in range(current_year - 1, current_year - 4, -1):
            financials = await self._fetch_financials_for_year(orgnr, year)
            if financials: return financials
        return None

    async def get_comprehensive_company_info(self, orgnr: str) -> ComprehensiveCompanyInfo:
        tasks = [self.get_company_details(orgnr), self.get_signature_info(orgnr), self.get_latest_available_financials(orgnr)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        details_res, signature_res, financials_res = [res if not isinstance(res, Exception) else None for res in results]
        return ComprehensiveCompanyInfo(details=details_res, signature=signature_res, financials=financials_res)