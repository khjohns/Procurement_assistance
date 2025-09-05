# procurement.py
import yaml
import asyncio
import structlog
from typing import List
from dotenv import load_dotenv
import os
import json
import logging

from datetime import datetime, timedelta

# Konfigurer logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        # ConsoleRenderer er nøkkelen til pen output med farger
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(min_level=logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False
)

# Importer agenter og modeller
from src.agents.oslomodell_agent import OslomodellAgent
from src.models.base_models import BaseProcurementInput, BaseAssessment, RiskAssessmentItem
from src.models.enums import ProcurementCategory, ProcurementSubCategory, RiskType, RiskLevel

# --- NYTT: Importer den nye notat-generatoren ---
from src.generators.procurement_note_generator import ProcurementNoteGenerator

async def process_single_procurement(
    procurement_input: BaseProcurementInput,
    agent: OslomodellAgent,
    note_generator: ProcurementNoteGenerator, # Ny parameter
    index: int
    ):
    """
    Kjører hele prosessen for én enkelt anskaffelse og genererer et anskaffelsesnotat.
    """
    print(f"\n--- Starter prosessering for test {index}: '{procurement_input.name}' ---")
    log = structlog.get_logger().bind(procurement_name=procurement_input.name)
    
    try:
        # Steg 1: Kjør den fulle agent-vurderingen
        log.info("agent_assessment_started")
        assessment_result = await agent.assess(procurement_input)
        log.info("agent_assessment_finished")

        # Steg 2: Generer anskaffelsesnotatet som en Markdown-fil
        output_filename = f"anskaffelsesnotat_test_{index}.md" # <--- ENDRING: .md i stedet for .docx
        log.info("note_generation_started", output_file=output_filename)
        
        note_generator.generate(
            procurement=procurement_input,
            assessment=assessment_result,
            output_path=output_filename
        )
        
        print(f"✅ Vellykket! Anskaffelsesnotat generert: '{output_filename}'")

    except Exception as e:
        print(f"❌ FEIL under prosessering av '{procurement_input.name}': {e}")
        log.exception("procurement_processing_failed")


# ==============================================================================
# HOVEDFUNKSJON
# ==============================================================================
async def main():
    """Laster konfig, initialiserer agenter, og kjører alle tester."""
    
    # 1. Last konfigurasjon
    print("Laster konfigurasjon fra 'config/oslomodell_config.yaml'...")
    try:
        with open("config/oslomodell_config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"FEIL: Kunne ikke lese konfigurasjonsfilen: {e}")
        return

    load_dotenv()
    
    # 2. Initialiser agenter og verktøy
    print("Initialiserer OslomodellAgent og Notat-generator...")
    try:
        agent = OslomodellAgent(config)
        note_generator = ProcurementNoteGenerator()
    except Exception as e:
        print(f"FEIL: Kunne ikke initialisere: {e}")
        return

    # Definer varierte test-caser
    print("Definerer test-anskaffelser...")
    test_procurements: List[BaseProcurementInput] = [
        # TEST A: Høyrisiko Bygg & Anlegg
        BaseProcurementInput(
            name="Rehabilitering av Storgata Skole",
            value=25_000_000,
            category=ProcurementCategory.CONSTRUCTION,
            duration_months=18,
            description="Totalrehabilitering av skolebygg. Omfatter tømrer, rørlegger, og elektrikerarbeid, samt utskifting av ventilasjonsanlegg.",
            requested_by="Eiendomsetaten",
            case_number="24/812",
            risk_assessments=[
                RiskAssessmentItem(type=RiskType.LABOR_CRIME, level=RiskLevel.HIGH),
                RiskAssessmentItem(type=RiskType.SOCIAL_DUMPING, level=RiskLevel.HIGH)
            ]
        ),
        
        # TEST B: Lavverdi Varekjøp
        BaseProcurementInput(
            name="Innkjøp av kontorrekvisita for 2025",
            value=80_000,
            category=ProcurementCategory.GOODS,
            duration_months=1,
            description="Standard kontorrekvisita som penner, papir og permer til administrasjonen.",
            requested_by="Servicesenteret",
            case_number="24/813",
        ),
        
        # TEST C: Tjeneste med spesialregel (Reservert kontrakt)
        BaseProcurementInput(
            name="Ny fruktordning for Rådhuset",
            value=600_000,
            category=ProcurementCategory.SERVICE,
            subcategory=ProcurementSubCategory.FRUIT,
            duration_months=12,
            description="Levering av fruktkurver til ansatte i Rådhuset, to ganger i uken.",
            requested_by="Byrådsavdelingen",
            case_number="24/814",
            risk_assessments=[
                RiskAssessmentItem(type=RiskType.SOCIAL_DUMPING, level=RiskLevel.MEDIUM)
            ]
        ),
        # TEST D: Direkteanskaffelse, middels verdi (med leverandør)
        BaseProcurementInput(
            name="Innkjøp av konsulentbistand til prosjekt X",
            value=250_000,
            category=ProcurementCategory.SERVICE,
            duration_months=3,
            description="Spesialisert teknisk bistand...",
            requested_by="IT-avdelingen",
            case_number="24/815",
            # --- KORREKSJON: Bruk et ekte firmanavn for entydig treff ---
            supplier_name_to_verify="Atea AS",
            risk_assessments=[
                RiskAssessmentItem(type=RiskType.SOCIAL_DUMPING, level=RiskLevel.LOW)
            ]
        ),

        # TEST E: Direkteanskaffelse, høy verdi (med leverandør)
        BaseProcurementInput(
            name="Hasteutbedring av vannlekkasje",
            value=750_000,
            category=ProcurementCategory.CONSTRUCTION,
            duration_months=1,
            description="Akutt reparasjon av rørbrudd...",
            requested_by="Driftsavdelingen",
            case_number="24/902",
            # --- KORREKSJON: Bruk et ekte firmanavn for entydig treff ---
            supplier_name_to_verify="Betonmast Oslo AS",
            risk_assessments=[
                RiskAssessmentItem(type=RiskType.SOCIAL_DUMPING, level=RiskLevel.LOW)
            ]
        )
    ]

    print(f"\n{'='*30} STARTER PROSESSERING AV {len(test_procurements)} ANSKAFFELSER {'='*30}")
    
    tasks = [
        process_single_procurement(proc, agent, note_generator, i + 1)
        for i, proc in enumerate(test_procurements)
    ]
    
    await asyncio.gather(*tasks)
    
    print(f"\n{'='*30} PROSESSERING FULLFØRT {'='*30}")
    
    await agent.http_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())