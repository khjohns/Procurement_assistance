# main.py
import yaml
import asyncio
import structlog
import httpx
import os
from typing import Dict

# Importer de relevante klassene (SanctionsAgent er fjernet)
from src.agents.obs_list_agent import ObsListAgent, VerificationStatus, VerificationResult
from src.services.brreg_service import BrregService
from src.analyzers.company_analyzer import CompanyAnalyzer
from src.tools.company_report_tool import CompanyReportTool

# Konfigurer logging for penere output i terminalen
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()


async def handle_interactive_verification(
    obs_agent: ObsListAgent, 
    report_tool: CompanyReportTool,
    supplier_name: str, 
    is_foreign: bool
):
    """
    Håndterer den interaktive, tostegs verifiseringsflyten.
    """
    print("\n" + "="*50)
    print(f"🔍 Starter verifisering for: '{supplier_name}'")
    print("="*50)

    # --- STEG 1: Utfør det initielle søket ---
    initial_result = await obs_agent.verify_supplier(supplier_name=supplier_name, is_foreign=is_foreign)
    
    final_result_to_check = initial_result
    org_nr_to_check = None
    official_name = ""

    # Håndter valg fra bruker hvis det er flere treff
    if initial_result.status == VerificationStatus.NEEDS_SELECTION:
        print(f"📋 {initial_result.message}")
        for i, option in enumerate(initial_result.options, 1):
            print(f"  {i}. {option['display_text']}")
        print("  0. Avbryt")

        try:
            choice = int(input(f"\nVelg korrekt leverandør (0-{len(initial_result.options)}): "))
            if choice == 0:
                print("❌ Avbrutt av bruker."); return
            if 1 <= choice <= len(initial_result.options):
                selected = initial_result.options[choice - 1]
                org_nr_to_check = selected['orgnr']
                official_name = selected['navn']
                print(f"\nDu valgte '{official_name}'. Utfører endelig sjekk...")
                # Utfør den endelige sjekken
                final_result_to_check = await obs_agent.verify_selected_company(org_nr_to_check)
            else:
                print("Ugyldig valg."); return
        except ValueError:
            print("Ugyldig input."); return
    
    # Vis det endelige resultatet fra OBS-sjekken
    print("\n--- RESULTAT FRA OBS-LISTE ---")
    print(obs_agent.format_result_for_display(final_result_to_check))

    # Fortsett KUN hvis den endelige statusen er OK
    if final_result_to_check.status == VerificationStatus.OK:
        org_nr = final_result_to_check.metadata.get('organisasjonsnummer')
        name = final_result_to_check.metadata.get('navn')
        
        print("\n" + "="*50)
        print(f"📊 OBS-sjekk OK. Genererer full selskapsrapport for '{name}'...")
        print("="*50)
        
        try:
            report = await report_tool.generate_report(orgnr=org_nr, official_name=name)
            print(report)
        except Exception as e:
            log.error("Klarte ikke å generere selskapsrapport", error=str(e), exc_info=True)
    else:
        log.warning("Prosessen stoppet. Selskapsrapport genereres ikke.")

async def main():
    """Hovedfunksjon for å kjøre den interaktive verifisereren."""
    print("Laster konfigurasjon...")
    try:
        with open("config/oslomodell_config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"FEIL: Kunne ikke lese 'oslomodell_config.yaml': {e}"); return

    print("Initialiserer tjenester og verktøy...")
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as http_client:
        # Initialiser tjenester med de spesifikke URL-ene fra config
        brreg_service = BrregService(
            http_client=http_client,
            enhetsregisteret_url=config["external_services"]["brreg_enhetsregisteret_url"],
            regnskapsregisteret_url=config["external_services"]["brreg_regnskapsregisteret_url"],
            fullmakt_api_url=config["external_services"]["brreg_fullmakt_api_url"]
        )
        
        # Initialiser OBS-agent
        obs_agent = ObsListAgent(brreg_service, "data/OBS_listen.csv")
        
        # Initialiser analyse- og rapportverktøy
        analyzer = CompanyAnalyzer(config.get("company_analyzer_config", {}))
        report_tool = CompanyReportTool(brreg_service=brreg_service, analyzer=analyzer)

        # Start interaktivt grensesnitt
        print("\n" + "="*60)
        print(" VELKOMMEN TIL SAMLET LEVERANDØR-VERIFISERING")
        print(" (OBS-liste & Selskapsanalyse)")
        print("="*60)

        while True:
            print("\nVelg en handling:")
            print(" 1. Verifiser en norsk leverandør")
            print(" 2. Registrer en utenlandsk leverandør (kun OBS-sjekk)")
            print(" 0. Avslutt")
            
            choice = input("Ditt valg: ")
            if choice == '1':
                supplier_name = input("Skriv inn navnet på den norske leverandøren: ")
                if supplier_name:
                    await handle_interactive_verification(
                        obs_agent, report_tool, supplier_name, is_foreign=False
                    )
            elif choice == '2':
                supplier_name = input("Skriv inn navnet på den utenlandske leverandøren: ")
                if supplier_name:
                    await handle_interactive_verification(
                        obs_agent, report_tool, supplier_name, is_foreign=True
                    )
            elif choice == '0':
                print("\nAvslutter programmet."); break
            else:
                print("Ugyldig valg.")

if __name__ == "__main__":
    asyncio.run(main())