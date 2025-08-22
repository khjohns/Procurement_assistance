# main.py
import yaml
import asyncio
import structlog
from typing import List

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
from src.reporting.protocol_generator import ProtocolGenerator
from src.reporting.report_converter import ReportConverter

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


# --- Hovedfunksjon for å kjøre agenten ---
async def main():
    """Laster konfig, initialiserer agenten, og kjører tester."""
    
    # 1. Last konfigurasjon
    print("Laster konfigurasjon fra 'config/oslomodell_config.yaml'...")
    try:
        with open("config/oslomodell_config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("FEIL: Konfigurasjonsfilen 'config/oslomodell_config.yaml' ble ikke funnet.")
        return
    except Exception as e:
        print(f"FEIL: Kunne ikke lese konfigurasjonsfilen: {e}")
        return
    
    # 2.A Initialiser Oslomodellagenten
    print("Initialiserer OslomodellAgent...")
    try:
        agent = OslomodellAgent(config)
    except Exception as e:
        print(f"FEIL: Kunne ikke initialisere agenten: {e}")
        return

    # 2.B Initialiser ProtocolGenerator
    print("Initialiserer rapport-verktøy...")
    try:
        protocol_generator = ProtocolGenerator("config/protocol_config.yaml")
        report_converter = ReportConverter()
    except Exception as e:
        print(f"FEIL: Kunne ikke initialisere ProtocolGenerator: {e}")
        return

    
    # 3. Definer nye, målrettede test-anskaffelser for den oppdaterte lærling-agenten
    print("Definerer test-anskaffelser for den oppdaterte lærling-agenten...")
    
    test_procurements: List[BaseProcurementInput] = [
        BaseProcurementInput(
            name="Totalrehabilitering av gymsal på Majorstuen Skole",
            value=5_000_000,
            category=ProcurementCategory.CONSTRUCTION,
            duration_months=12,
            description="Prosjektet omfatter full rehabilitering av alle VVS-systemer, inkludert utskifting av rør og sanitærutstyr. I tillegg skal det utføres omfattende tømrerarbeid med utskifting av vegger og takkonstruksjoner.",
            # <--- START ENDRING: Legg til data for de nye feltene ---
            requested_by="Kari Nordmann, Prosjektleder",
            case_number="25/463",
            project_number="P-102-MAJ",
            tender_deadline=datetime.now() + timedelta(days=30)
            # <--- SLUTT ENDRING ---
        )
    ]

    # 4. Kjør vurdering for hver test-anskaffelse
    for i, procurement_input in enumerate(test_procurements):
        print(f"\n--- Kjører test {i+1}: '{procurement_input.name}' ---")
        try:
            assessment_result = await agent.assess(procurement_input)
            #print_assessment_summary(assessment_result)

            # Steg A: Generer Markdown-innholdet
            protocol_markdown = protocol_generator.generate(assessment_result, procurement_input)
            
            print("\n" + "="*80)
            print("GENERERT MARKDOWN-RAPPORT (UTDRAG):")
            print("\n".join(protocol_markdown.splitlines()[:15])) # Viser kun de første 15 linjene
            print("...")
            print("="*80 + "\n")

            base_filename = f"rapport_{procurement_input.name.replace(' ', '_').lower()}"
            md_filename = base_filename + ".md"
            
            with open(md_filename, "w", encoding="utf-8") as f:
                f.write(protocol_markdown)
            print(f"Kvalitetssikring: Mellomliggende Markdown-fil lagret som '{md_filename}'")

            # Steg B: Konverter til Word og PDF
            docx_filename = base_filename + ".docx"
            pdf_filename = base_filename + ".pdf"
            
            print(f"Rapporter for '{procurement_input.name}' er ferdig generert.")

            #docx_template = protocol_generator.config.get("formatting", {}).get("docx_template")
            pdf_font = protocol_generator.config.get("formatting", {}).get("pdf_font", "Calibri")

            print(f"Konverterer rapport til Word-format: '{docx_filename}'...")
            #report_converter.to_docx(protocol_markdown, docx_filename, reference_docx=docx_template)
            report_converter.to_docx(protocol_markdown, docx_filename)

            print(f"Konverterer rapport til PDF-format: '{pdf_filename}'...")
            report_converter.to_pdf(protocol_markdown, pdf_filename, font=pdf_font)

        except Exception as e:
            print(f"FEIL under kjøring av vurdering for '{procurement_input.name}': {e}")
            # I en reell applikasjon, logg hele traceback
            structlog.get_logger().exception("assessment_run_failed")
            
    # 5. Rens opp ressurser
    await agent.http_client.aclose()


if __name__ == "__main__":
    # Kjør async hovedfunksjon
    asyncio.run(main())