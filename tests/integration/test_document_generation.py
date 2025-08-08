#!/usr/bin/env python3
"""
test_document_generation.py
Test som kjører Oslomodell-agent og genererer dokument basert på resultatet.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.enhanced_llm_gateway import LLMGateway
from src.tools.embedding_gateway import EmbeddingGateway
from src.specialists.oslomodell_agent import OslomodellAgent
from src.models.procurement_models import ProcurementRequest, ProcurementCategory
from src.tools.oslomodell_document_generator import OslomodellDocumentGenerator

load_dotenv()

async def test_with_real_assessment():
    """
    Kjører faktisk Oslomodell-vurdering og genererer dokument.
    """
    print("\n" + "="*60)
    print("📄 TEST: Oslomodell Document Generation")
    print("="*60 + "\n")
    
    # 1. Initialiser komponenter
    print("1️⃣ Initialiserer komponenter...")
    llm_gateway = LLMGateway()
    embedding_gateway = EmbeddingGateway(api_key=os.getenv("GEMINI_API_KEY"))
    oslomodell_agent = OslomodellAgent(llm_gateway, embedding_gateway)
    document_generator = OslomodellDocumentGenerator("test_documents")
    
    # 2. Definer test-anskaffelser
    test_cases = [
        {
            "name": "Rammeavtale renhold kommunale bygg",
            "value": 4_500_000,
            "category": ProcurementCategory.RENHOLD,
            "duration_months": 24,
            "description": "Renhold av 15 kommunale bygg inkludert skoler og barnehager. Daglig renhold, hovedrengjøring og vinduspuss."
        },
        {
            "name": "Konsulentbistand digitalisering",
            "value": 2_800_000,
            "category": ProcurementCategory.KONSULENT,
            "duration_months": 12,
            "description": "Innleie av IT-konsulenter for digital transformasjon av saksbehandlingssystemer"
        },
        {
            "name": "Totalentreprise nytt sykehjem",
            "value": 125_000_000,
            "category": ProcurementCategory.BYGGE,
            "duration_months": 24,
            "description": "Bygging av nytt sykehjem med 120 plasser, inkludert all infrastruktur og uteområder"
        }
    ]
    
    generated_files = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'-'*60}")
        print(f"Test case {i}/{len(test_cases)}: {test_case['name']}")
        print(f"Verdi: {test_case['value']:,} NOK | Kategori: {test_case['category'].value}")
        print(f"{'-'*60}")
        
        # 3. Kjør Oslomodell-vurdering
        print("\n2️⃣ Kjører Oslomodell-vurdering...")
        
        procurement = ProcurementRequest(**test_case)
        
        try:
            assessment = await oslomodell_agent.execute({
                "procurement": procurement.model_dump()
            })
            
            print(f"✅ Vurdering fullført:")
            print(f"   - Risiko: {assessment.get('vurdert_risiko_for_akrim')}")
            print(f"   - Antall krav: {len(assessment.get('påkrevde_seriøsitetskrav', []))}")
            print(f"   - Underleverandørledd: {assessment.get('anbefalt_antall_underleverandørledd')}")
            print(f"   - Lærlinger påkrevd: {assessment.get('krav_om_lærlinger', {}).get('status')}")
            
            # 4. Generer dokument
            print("\n3️⃣ Genererer dokument...")
            
            filepath = document_generator.generate_document(
                procurement_data=procurement.model_dump(),
                oslomodell_assessment=assessment,
                additional_context={
                    "generated_by": "test_document_generation.py",
                    "test_run": True
                }
            )
            
            generated_files.append(filepath)
            print(f"✅ Dokument generert: {filepath}")
            
            # 5. Les og vis utdrag
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            print("\n📄 Utdrag fra dokumentet:")
            print("-" * 40)
            # Vis første 20 linjer
            for line in lines[:20]:
                print(line)
            print("...")
            print(f"(Totalt {len(lines)} linjer)")
            
        except Exception as e:
            print(f"❌ Feil: {e}")
            import traceback
            traceback.print_exc()
    
    # 6. Generer oppsummeringstabell
    print("\n" + "="*60)
    print("4️⃣ Genererer oppsummeringstabell...")
    
    # Samle alle vurderinger
    all_assessments = []
    for i, test_case in enumerate(test_cases):
        # Her ville vi normalt hente fra faktiske resultater
        # For demo bruker vi placeholder
        all_assessments.append({
            "procurement": test_case,
            "assessment": {
                "vurdert_risiko_for_akrim": ["høy", "lav", "høy"][i],
                "påkrevde_seriøsitetskrav": [
                    ["A", "B", "C", "D", "E"] if i == 1 
                    else ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"]
                ][0],
                "anbefalt_antall_underleverandørledd": [1, 2, 1][i],
                "krav_om_lærlinger": {"status": i != 1}
            }
        })
    
    summary_table = document_generator.generate_summary_table(all_assessments)
    print("\n" + summary_table)
    
    # 7. Lagre oppsummering
    summary_file = Path("test_documents") / "OPPSUMMERING.md"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("# Oppsummering - Oslomodell vurderinger\n\n")
        f.write(f"Generert: {datetime.now().strftime('%d.%m.%Y kl. %H:%M')}\n\n")
        f.write(summary_table)
        f.write("\n\n## Genererte dokumenter\n\n")
        for filepath in generated_files:
            f.write(f"- [{Path(filepath).name}]({Path(filepath).name})\n")
    
    print(f"\n✅ Oppsummering lagret: {summary_file}")
    
    print("\n" + "="*60)
    print("✅ TEST FULLFØRT")
    print(f"Genererte {len(generated_files)} dokumenter")
    print(f"Se mappen: test_documents/")
    print("="*60)

async def test_from_orchestration_context():
    """
    Test med simulert orchestration context.
    """
    print("\n📋 Test med orchestration context...")
    
    # Simuler en orchestration context
    mock_context = {
        "current_state": {
            "request": {
                "id": "mock-123",
                "name": "Test anskaffelse",
                "value": 5_000_000,
                "category": "tjeneste",
                "duration_months": 12,
                "description": "Test beskrivelse"
            }
        },
        "execution_history": [
            {
                "action": {"method": "database.create_procurement"},
                "result": {"status": "success"}
            },
            {
                "action": {"method": "agent.run_oslomodell"},
                "result": {
                    "status": "success",
                    "result": {
                        "vurdert_risiko_for_akrim": "moderat",
                        "påkrevde_seriøsitetskrav": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
                        "anbefalt_antall_underleverandørledd": 1,
                        "krav_om_lærlinger": {"status": False, "begrunnelse": "Under terskelverdi"},
                        "confidence": 0.9
                    }
                }
            }
        ]
    }
    
    from oslomodell_document_generator import generate_from_orchestration
    
    filepath = await generate_from_orchestration(mock_context)
    print(f"✅ Generated from context: {filepath}")

if __name__ == "__main__":
    from datetime import datetime
    
    # Kjør hovedtest
    asyncio.run(test_with_real_assessment())
    
    # Kjør context-test
    # asyncio.run(test_from_orchestration_context())