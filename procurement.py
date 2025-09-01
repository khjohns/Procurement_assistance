# main.py
import yaml
import asyncio
import structlog
from typing import List
from dotenv import load_dotenv
import os
import json

from datetime import datetime, timedelta

# Konfigurer logging for pen output i konsollen
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

# Importer agent og modeller
from src.agents.oslomodell_agent import OslomodellAgent
from src.agents.obs_list_agent import ObsListAgent

from src.reporting.protocol_generator import ProtocolGenerator
from src.reporting.report_converter import ReportConverter

from src.services.brreg_service import BrregService

from src.models.base_models import BaseProcurementInput, BaseAssessment
from src.models.enums import ProcurementCategory, ProcurementSubCategory

# --- Hjelpefunksjon for å printe resultater ---
def print_assessment_summary(assessment: BaseAssessment):
    """Printer en formatert oppsummering av en BaseAssessment."""
    
    print("\n" + "="*80)
    print(f" VURDERINGS-RAPPORT FOR: {assessment.procurement_name}")
    print(f" Anskaffelses-ID: {assessment.procurement_id}")
    print(f" Vurderings-ID:    {assessment.assessment_id}")
    print(f" Agent:             {assessment.agent_name}")
    print(f" Vurderingstidspunkt: {assessment.assessment_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 1. Sammendrag av anvendelige krav
    print(f"\n--- ANVENDELIGE KRAV ({len(assessment.applicable_requirements)}) ---")
    if not assessment.applicable_requirements:
        print("Ingen spesifikke krav ble aktivert.")
    else:
        for req in assessment.applicable_requirements:
            print(f"  - [{req.code}] {req.name} (Kilde: {req.source.value}, Kategori: {req.category.value})")

    # 2. Utløste regler
    print(f"\n--- UTLØSTE REGLER ({len(assessment.triggered_rules)}) ---")
    if not assessment.triggered_rules:
        print("Ingen regler ble utløst.")
    else:
        for rule in assessment.triggered_rules:
            print(f"  - Regel '{rule.rule_id}': {rule.description}")

    # 3. Anbefalinger og advarsler
    print("\n--- ANBEFALINGER OG ADVARSLER ---")
    if assessment.recommendations:
        print("Anbefalinger:")
        for rec in assessment.recommendations:
            print(f"  - {rec}")
    if assessment.warnings:
        print("Advarsler:")
        for warn in assessment.warnings:
            print(f"  - {warn}")
    if not assessment.recommendations and not assessment.warnings:
        print("Ingen spesifikke anbefalinger eller advarsler.")

    # 4. Detaljert begrunnelse (Reasoning Steps)
    print("\n--- DETALJERT BEGRUNNELSE (AGENTENS RESSENOMENT) ---")
    if not assessment.reasoning_steps:
        print("Ingen detaljert begrunnelse tilgjengelig.")
    else:
        for step in assessment.reasoning_steps:
            print(f"  {step}")

    print("\n" + "="*80 + "\n")

async def process_single_procurement(
    procurement_input: BaseProcurementInput,
    agent: OslomodellAgent,
    protocol_generator: ProtocolGenerator,
    report_converter: ReportConverter,
    index: int
    ):
    """
    Kjører hele prosessen for én enkelt anskaffelse.
    Denne funksjonen er designet for å kunne kjøres parallelt med andre.
    """
    print(f"\n--- Starter prosessering for test {index}: '{procurement_input.name}' ---")
    try:
        # Steg 1: Kjør vurderingen
        assessment_result = await agent.assess(procurement_input)
        print_assessment_summary(assessment_result)


        """
        # Steg 2: Generer rapport-innhold
        protocol_markdown = protocol_generator.generate(assessment_result, procurement_input)
        
        print("\n" + "="*80)
        print(f"GENERERER RAPPORT-FILER FOR '{procurement_input.name}'...")
        
        base_filename = f"rapport_test_{index}"
        md_filename = base_filename + ".md"
        
        # Steg 3: Lagre filer (merk: fil-I/O er blokkerende, men fordelen er fortsatt stor)
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(protocol_markdown)
        print(f"  - Markdown-fil lagret som '{md_filename}'")

        docx_filename = base_filename + ".docx"
        pdf_filename = base_filename + ".pdf"
        
        pdf_font = protocol_generator.config.get("formatting", {}).get("pdf_font", "Calibri")

        report_converter.to_docx(protocol_markdown, docx_filename)
        print(f"  - Word-fil lagret som '{docx_filename}'")

        report_converter.to_pdf(protocol_markdown, pdf_filename, font=pdf_font)
        print(f"  - PDF-fil lagret som '{pdf_filename}'")
        print("="*80 + "\n")
        """
    except Exception as e:
        print(f"FEIL under parallell prosessering av '{procurement_input.name}': {e}")
        structlog.get_logger().exception("parallel_assessment_run_failed", procurement_name=procurement_input.name)


# ==============================================================================
# OPPDATERT HOVEDFUNKSJON
# ==============================================================================
async def main():
    """Laster konfig, initialiserer agenten, og kjører alle tester parallelt."""
    
    # 1. Last konfigurasjon (uendret)
    print("Laster konfigurasjon fra 'config/oslomodell_config.yaml'...")
    try:
        with open("config/oslomodell_config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"FEIL: Kunne ikke lese konfigurasjonsfilen: {e}")
        return

    load_dotenv()
    
    # 2. Initialiser agenter og verktøy (uendret)
    print("Initialiserer OslomodellAgent og rapport-verktøy...")
    try:
        agent = OslomodellAgent(config)
        protocol_generator = ProtocolGenerator("config/protocol_config.yaml")
        report_converter = ReportConverter()
    except Exception as e:
        print(f"FEIL: Kunne ikke initialisere: {e}")
        return


    # ==============================================================================
    # SEKSJON FOR TESTING AV OBS-LISTE AGENT
    # ==============================================================================
    print("\n" + "="*80)
    print("INITIALISERER OG TESTER OBS-LISTE AGENT")
    print("="*80)

    # Gjenbruk http-klienten fra OslomodellAgent for effektivitet
    brreg_service = BrregService(agent.http_client, config['external_services']['brreg_api_url'])
    
    # Initialiser den nye agenten med sti til datafilen
    obs_agent = ObsListAgent(brreg_service, "data/OBS_listen.csv")

    # Definer test-caser som dekker alle scenarioer
    test_suppliers = [
        {"name": "OSLOBYGG KF", "is_foreign": False}, # Forventer "OK"
        {"name": "RENHOLD PLUSS AS", "is_foreign": False}, # Antatt treff i OBS-listen
        {"name": "Aker", "is_foreign": False}, # Forventer "FLERE TREFF"
        {"name": "Ikke Eksisterende Firma AS", "is_foreign": False}, # Forventer "FEIL"
        {"name": "Global Construction Ltd", "is_foreign": True}, # Forventer "ADVARSEL" for utenlandsk
    ]
    
    print("\nKjører verifisering for flere leverandører...")
    for supplier in test_suppliers:
        print(f"\n--- Sjekker: '{supplier['name']}' (Utenlandsk: {supplier['is_foreign']}) ---")
        result = await obs_agent.verify_supplier(supplier['name'], supplier['is_foreign'])
        print(result)
        print("----------------------------------------------------")


    # 3. Definer alle test-anskaffelser (uendret)
    print("Definerer test-anskaffelser...")
    test_procurements: List[BaseProcurementInput] = [
        # TEST A: Vare med høy risiko for menneskerettigheter
        # Forventer: Menneskerettighetsrisiko -> HØY (fra mock_logic)
        #            Korrupsjonsrisiko -> MODERAT (fra mock_risk_assessment)
        #            AKTSOMHET-A skal utløses.  
        BaseProcurementInput(
            name="Test A: Innkjøp av 1000 nettbrett til sykehjem",
            value=1_500_000,
            category=ProcurementCategory.GOODS,
            duration_months=4,
            description="Anskaffelse av nettbrett for pasientkommunikasjon. Elektronikk har kjente utfordringer i leverandørkjeden.",
            requested_by="Helseetaten",
            case_number="25/201",
        )
        ]

    print(f"\n{'='*30} STARTER PARALLELL PROSESSERING AV {len(test_procurements)} ANSKAFFELSER {'='*30}")
    
    # Lag en liste med oppgaver, én for hver anskaffelse
    tasks = [
        process_single_procurement(proc, agent, protocol_generator, report_converter, i + 1)
        for i, proc in enumerate(test_procurements)
    ]
    
    # Kjør alle oppgavene samtidig og vent til alle er ferdige
    await asyncio.gather(*tasks)
    
    print(f"\n{'='*30} PARALLELL PROSESSERING FULLFØRT {'='*30}")
    
    # 5. Rens opp ressurser
    await agent.http_client.aclose()


if __name__ == "__main__":
    # Kjør async hovedfunksjon
    asyncio.run(main())