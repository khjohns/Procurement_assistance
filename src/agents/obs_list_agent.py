# Forbedret src/agents/obs_list_agent.py
import csv
from typing import Dict, Any, Optional, List, Tuple
import structlog
from enum import Enum

from src.services.brreg_service import BrregService

logger = structlog.get_logger()

class VerificationStatus(Enum):
    """Status-koder for verifiseringsresultater"""
    OK = "OK"
    WARNING = "ADVARSEL"
    ERROR = "FEIL"
    MULTIPLE_MATCHES = "FLERE_TREFF"
    NEEDS_SELECTION = "VELG_LEVERANDØR"

class VerificationResult:
    """Strukturert resultat fra verifisering"""
    def __init__(self, status: VerificationStatus, message: str, 
                 options: Optional[List[Dict]] = None, metadata: Optional[Dict] = None):
        self.status = status
        self.message = message
        self.options = options or []
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "message": self.message,
            "options": self.options,
            "metadata": self.metadata
        }

class ObsListAgent:
    """
    En deterministisk agent for å verifisere leverandører mot en OBS-liste.
    Forbedret med strukturert håndtering av flere treff.
    """
    def __init__(self, brreg_service: BrregService, obs_list_path: str):
        """
        Initialiserer agenten.

        Args:
            brreg_service: En instans av BrregService for å normalisere norske firmanavn.
            obs_list_path: Stien til CSV-filen som inneholder OBS-listen.
        """
        self.brreg_service = brreg_service
        self.obs_data = self._load_obs_list(obs_list_path)

    def _load_obs_list(self, file_path: str) -> Dict[str, Dict[str, str]]:
        """
        Laster OBS-listen fra en semikolon-separert CSV-fil inn i en dictionary
        for raske oppslag basert på organisasjonsnummer.
        """
        log = logger.bind(file_path=file_path)
        log.info("loading_obs_list")
        
        obs_dict = {}
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as infile:
                reader = csv.DictReader(infile, delimiter=';')
                for row in reader:
                    org_nr_raw = row.get('Org.nummer')
                    if org_nr_raw:
                        # NY OG FORBEDRET LINJE:
                        # Beholder kun sifre (0-9) og fjerner absolutt alt annet.
                        org_nr_cleaned = "".join(filter(str.isdigit, org_nr_raw))
                        
                        # Legg til en ekstra sjekk for å sikre at vi har et gyldig org.nr.
                        if len(org_nr_cleaned) == 9:
                            obs_dict[org_nr_cleaned] = {
                                "Navn": row.get('Navn', ''),
                                "Merknad": row.get('Merknad', 'Ingen merknad angitt.')
                            }
                        else:
                            # Logger en advarsel hvis vi finner en ugyldig rad
                            log.warning("invalid_org_nr_in_obs_list_skipped", raw_value=org_nr_raw)
            log.info("obs_list_loaded_successfully", count=len(obs_dict))

            # === START DEBUGGING-KODE ===
            print("\n" + "="*25 + " DEBUG: INNLASING AV OBS-LISTE " + "="*25)
            print(f"Fant og lastet {len(obs_dict)} rader fra {file_path}.")
            print("Viser de 5 første organisasjonsnumrene slik de er lagret i minnet:")
            
            # Hent de første 5 nøklene for inspeksjon
            first_five_keys = list(obs_dict.keys())[:5]
            for i, key in enumerate(first_five_keys):
                # Vi printer nøkkelen, dens datatype, og dens lengde for å avsløre skjulte tegn
                print(f"  - Nøkkel {i+1}: '{key}' (Type: {type(key)}, Lengde: {len(key)})")
            print("="*78 + "\n")
            # === SLUTT DEBUGGING-KODE ===

            return obs_dict
        except FileNotFoundError:
            log.error("obs_list_file_not_found")
            return {}
        except Exception as e:
            log.error("failed_to_load_or_parse_obs_list", error=str(e))
            return {}

    async def verify_supplier(
        self, 
        supplier_name: str, 
        is_foreign: bool = False,
        auto_select_single: bool = True
    ) -> VerificationResult:
        """
        Kjører den stegvise, deterministiske verifiseringen av en leverandør.
        
        Args:
            supplier_name: Navn på leverandøren
            is_foreign: Om leverandøren er utenlandsk
            auto_select_single: Om enkeltreff skal velges automatisk
            
        Returns:
            VerificationResult med status og eventuelt valg-alternativer
        """
        # Trinn 1: Håndtering av Utenlandske Leverandører
        if is_foreign:
            return VerificationResult(
                status=VerificationStatus.WARNING,
                message="Leverandøren er markert som utenlandsk. Siden organisasjonsnummer mangler, "
                       "kan ikke automatisk sjekk utføres. Bruker er ansvarlig for å sjekke "
                       "OBS-listen manuelt for denne leverandøren."
            )

        # Trinn 2: Normalisering via Brønnøysundregistrene
        log = logger.bind(supplier_name=supplier_name)
        log.info("obs_agent_normalizing_supplier_name")
        
        # Hent resultater med ekstra detaljer for bedre presentasjon
        brreg_results = await self.brreg_service.find_company(
            supplier_name, 
            size=10,  # Øk fra 5 til 10 for bedre dekning
            include_details=True
        )

        if not brreg_results:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Fant ingen leverandør med navnet '{supplier_name}' i Brønnøysundregistrene. "
                       "Kontroller navnet for skrivefeil. Hvis leverandøren er utenlandsk, "
                       "start prosessen på nytt og marker 'Utenlandsk leverandør'."
            )

        # Trinn 3: Håndter enkelt- eller flere treff
        if len(brreg_results) == 1 and auto_select_single:
            # Automatisk velg enkeltreff
            return await self._verify_single_company(brreg_results[0])
        
        elif len(brreg_results) > 1:
            # Flere treff - returner strukturert liste for brukervalg
            return self._create_multiple_matches_result(brreg_results, supplier_name)
        
        else:
            # Ett treff men auto_select er false - be om bekreftelse
            return self._create_confirmation_result(brreg_results[0])

    async def verify_selected_company(self, orgnr: str) -> VerificationResult:
        """
        Verifiserer en spesifikt valgt leverandør basert på organisasjonsnummer.
        
        Args:
            orgnr: Organisasjonsnummer for valgt leverandør
            
        Returns:
            VerificationResult med status fra OBS-sjekk
        """
        log = logger.bind(orgnr=orgnr)
        log.info("verifying_selected_company")
        
        # Hent detaljer om selskapet
        company_details = await self.brreg_service.get_company_details(orgnr)
        
        if not company_details:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Kunne ikke hente detaljer for organisasjonsnummer {orgnr}"
            )
        
        company_info = {
            "navn": company_details.navn,
            "orgnr": orgnr
        }
        
        return await self._verify_single_company(company_info)

    async def _verify_single_company(self, company: Dict[str, Any]) -> VerificationResult:
        """
        Intern metode for å verifisere ett enkelt firma mot OBS-listen.
        """
        official_name = company['navn']
        org_nr = company['orgnr']
        
        log = logger.bind(official_name=official_name, org_nr=org_nr)
        log.info("obs_agent_checking_obs_list")
        
        # Sjekk mot OBS-liste
        if org_nr in self.obs_data:
            merknad = self.obs_data[org_nr]['Merknad']
            return VerificationResult(
                status=VerificationStatus.WARNING,
                message=f"Leverandør '{official_name}' ({org_nr}) er funnet på OBS-listen.",
                metadata={
                    "merknad": merknad,
                    "organisasjonsnummer": org_nr,
                    "navn": official_name
                }
            )
        else:
            return VerificationResult(
                status=VerificationStatus.OK,
                message=f"Leverandør '{official_name}' (Org.nr: {org_nr}) er ikke funnet på OBS-listen.",
                metadata={
                    "organisasjonsnummer": org_nr,
                    "navn": official_name
                }
            )

    def _create_multiple_matches_result(
        self, 
        results: List[Dict], 
        search_term: str
    ) -> VerificationResult:
        """
        Lager strukturert resultat for flere treff.
        """
        # Formater alternativer med ekstra informasjon
        options = []
        for res in results:
            option = {
                "navn": res['navn'],
                "orgnr": res['orgnr'],
                "display_text": f"{res['navn']} ({res['orgnr']})"
            }
            
            # Legg til ekstra detaljer hvis tilgjengelig
            if 'organisasjonsform' in res:
                option['organisasjonsform'] = res['organisasjonsform']
                option['display_text'] += f" - {res['organisasjonsform']}"
            
            if 'poststed' in res and res['poststed']:
                option['poststed'] = res['poststed']
                option['display_text'] += f", {res['poststed']}"
            
            # Marker hvis konkurs eller under avvikling
            warnings = []
            if res.get('konkurs'):
                warnings.append("KONKURS")
            if res.get('underAvvikling'):
                warnings.append("UNDER AVVIKLING")
            
            if warnings:
                option['warnings'] = warnings
                option['display_text'] += f" ⚠️ {', '.join(warnings)}"
            
            options.append(option)
        
        message = (
            f"Søket etter '{search_term}' ga {len(results)} treff. "
            "Velg korrekt leverandør fra listen nedenfor:"
        )
        
        return VerificationResult(
            status=VerificationStatus.NEEDS_SELECTION,
            message=message,
            options=options,
            metadata={
                "search_term": search_term,
                "result_count": len(results)
            }
        )

    def _create_confirmation_result(self, company: Dict[str, Any]) -> VerificationResult:
        """
        Lager resultat som ber om bekreftelse for enkeltreff.
        """
        return VerificationResult(
            status=VerificationStatus.NEEDS_SELECTION,
            message=f"Fant leverandør: {company['navn']} ({company['orgnr']}). "
                   "Bekreft at dette er riktig leverandør.",
            options=[company],
            metadata={"needs_confirmation": True}
        )

    def format_result_for_display(self, result: VerificationResult) -> str:
        """
        Formaterer resultat for visning til bruker.
        
        Args:
            result: VerificationResult objekt
            
        Returns:
            Formatert streng for visning
        """
        output = []
        
        # Status-indikator
        status_icons = {
            VerificationStatus.OK: "✅",
            VerificationStatus.WARNING: "⚠️",
            VerificationStatus.ERROR: "❌",
            VerificationStatus.MULTIPLE_MATCHES: "🔍",
            VerificationStatus.NEEDS_SELECTION: "📋"
        }
        
        icon = status_icons.get(result.status, "")
        output.append(f"{icon} {result.status.value}: {result.message}")
        
        # Vis merknad hvis OBS-treff
        if result.status == VerificationStatus.WARNING and 'merknad' in result.metadata:
            output.append(f"\nMerknad: {result.metadata['merknad']}")
        
        # Vis alternativer hvis flere treff
        if result.options:
            output.append("\nAlternativer:")
            for i, option in enumerate(result.options, 1):
                output.append(f"  {i}. {option.get('display_text', option.get('navn', ''))}")
        
        return "\n".join(output)
