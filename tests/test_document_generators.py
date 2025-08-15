# test_document_generators.py
"""
Test-skript for alle dokumentgeneratorer.
Demonstrerer hvordan hver generator brukes med eksempeldata.
"""
import json
from datetime import datetime
from pathlib import Path

# Import all generators
from src.tools.oslomodel_document_generator import OslomodelDocumentGenerator
from src.tools.triage_document_generator import TriageDocumentGenerator
from src.tools.environmental_document_generator import EnvironmentalDocumentGenerator
from src.tools.orchestrated_document_generator import OrchestratedDocumentGenerator
from src.tools.comprehensive_document_generator import ComprehensiveDocumentGenerator

def create_test_data():
    """Oppretter testdata for alle generatorene."""
    
    # Felles procurement data
    procurement_data = {
        "id": "test-2025-001",
        "name": "Totalentreprise ny barnehage Majorstuen",
        "value": 35_000_000,
        "category": "bygge",
        "duration_months": 18,
        "description": "Bygging av ny 6-avdelings barnehage med uteområder, inkludert grunnarbeid og landskapsarkitektur",
        "includes_construction": True,
        "construction_site_size": 3500,
        "involves_demolition": True,
        "involves_earthworks": True,
        "involves_transport": True,
        "transport_type": "massetransport",
        "estimated_transport_volume": 2500
    }
    
    # Triage resultat
    triage_result = {
        "assessment_id": "triage-001",
        "color": "RØD",
        "reasoning": "Høy verdi (35M), byggeprosjekt med høy risiko for arbeidslivskriminalitet",
        "confidence": 0.95,
        "risk_factors": [
            "Høy kontraktsverdi over terskelverdi",
            "Bygge- og anleggssektor med kjent risiko",
            "Behov for mange underleverandører",
            "Inkluderer rivningsarbeid"
        ],
        "mitigation_measures": [
            "Grundig prekvalifisering av entreprenører",
            "Krav om medlemskap i StartBANK",
            "Stedlige kontroller under bygging",
            "Elektronisk adgangskontroll på byggeplass"
        ],
        "requires_special_attention": True,
        "escalation_recommended": False,
        "assessed_by": "triage_agent"
    }
    
    # Oslomodell resultat
    oslomodell_result = {
        "assessment_id": "oslo-001",
        "vurdert_risiko_for_akrim": "høy",
        "påkrevde_seriøsitetskrav": [
            "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
            "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V"
        ],
        "anbefalt_antall_underleverandørledd": 1,
        "aktsomhetsvurdering_kravsett": "A",
        "krav_om_lærlinger": {
            "status": True,
            "begrunnelse": "Over terskelverdi, varighet over 3 mnd, byggearbeid med behov for faglærte"
        },
        "recommendations": [
            "Gjennomfør grundig prekvalifisering av entreprenører",
            "Etabler rutiner for stedlig kontroll",
            "Bruk HMSREG aktivt i oppfølging",
            "Krev dokumentasjon på fast ansatte"
        ],
        "confidence": 0.92,
        "sources_used": ["oslo-instruks-2024", "oslomodell-veileder"],
        "assessed_by": "oslomodel_agent"
    }
    
    # Environmental resultat
    environmental_result = {
        "assessment_id": "env-001",
        "environmental_risk_level": "høy",
        "standard_miljokrav_applies": True,
        "reasoning": "Stort byggeprosjekt med betydelig miljøpåvirkning, massetransport og rivning",
        "transport_requirements": [
            {
                "requirement_type": "Utslippsfrie kjøretøy",
                "vehicle_class": "Tunge kjøretøy >3.5t",
                "deadline_date": "2027-01-01",
                "is_mandatory": False,
                "rationale": "Premiering frem til 2027, deretter krav"
            },
            {
                "requirement_type": "Utslippsfri massetransport",
                "vehicle_class": "Lastebiler for massetransport",
                "deadline_date": "2030-01-01",
                "is_mandatory": False,
                "rationale": "Premiering frem til 2030"
            }
        ],
        "additional_requirements": [
            "Krav om avfallssortering min. 90%",
            "Krav om gjenbruk av rivningsmaterialer",
            "Krav om miljøsertifisering ISO 14001",
            "Krav om klimagassregnskap"
        ],
        "exceptions": [],
        "recommendations": [
            "Gjennomfør tidlig markedsdialog om utslippsfrie løsninger",
            "Vurder innovasjonspartnerskap for nye løsninger",
            "Etabler system for klimagassrapportering",
            "Planlegg for elektrisk anleggsutstyr"
        ],
        "confidence": 0.88,
        "sources_used": ["miljokrav-instruks-2024"],
        "assessed_by": "environmental_agent"
    }
    
    # Simulert orchestration context
    orchestration_context = {
        "goal": {
            "id": "goal-001",
            "description": "Full compliance-vurdering for barnehageprosjekt",
            "status": "completed"
        },
        "current_state": {
            "request": procurement_data
        },
        "execution_history": [
            {
                "action": {"method": "database.create_procurement", "parameters": {"data": procurement_data}},
                "result": {"status": "success", "result": {"id": "test-2025-001"}}
            },
            {
                "action": {"method": "agent.run_triage", "parameters": {"procurement": procurement_data}},
                "result": {"status": "success", "result": triage_result}
            },
            {
                "action": {"method": "agent.run_oslomodell", "parameters": {"procurement": procurement_data}},
                "result": {"status": "success", "result": oslomodell_result}
            },
            {
                "action": {"method": "agent.run_environmental", "parameters": {"procurement": procurement_data}},
                "result": {"status": "success", "result": environmental_result}
            }
        ]
    }
    
    return {
        "procurement": procurement_data,
        "triage": triage_result,
        "oslomodell": oslomodell_result,
        "environmental": environmental_result,
        "context": orchestration_context
    }

def test_all_generators():
    """Tester alle dokumentgeneratorene."""
    
    print("="*60)
    print("TESTING ALL DOCUMENT GENERATORS")
    print("="*60)
    
    # Opprett testdata
    test_data = create_test_data()
    
    # Opprett output-mappe
    output_dir = "test_documents"
    Path(output_dir).mkdir(exist_ok=True)
    
    generated_files = []
    
    # Test 1: Oslomodell Generator
    print("\n1. Testing OslomodelDocumentGenerator...")
    oslo_gen = OslomodelDocumentGenerator(output_dir)
    oslo_file = oslo_gen.generate_document(
        test_data["procurement"], 
        test_data["oslomodell"]
    )
    print(f"   ✅ Generated: {oslo_file}")
    generated_files.append(oslo_file)
    
    # Test 2: Triage Generator
    print("\n2. Testing TriageDocumentGenerator...")
    triage_gen = TriageDocumentGenerator(output_dir)
    triage_file = triage_gen.generate_document(
        test_data["procurement"],
        test_data["triage"]
    )
    print(f"   ✅ Generated: {triage_file}")
    generated_files.append(triage_file)
    
    # Test 3: Environmental Generator
    print("\n3. Testing EnvironmentalDocumentGenerator...")
    env_gen = EnvironmentalDocumentGenerator(output_dir)
    env_file = env_gen.generate_document(
        test_data["procurement"],
        test_data["environmental"]
    )
    print(f"   ✅ Generated: {env_file}")
    generated_files.append(env_file)
    
    # Test 4: Orchestrated Generator
    print("\n4. Testing OrchestratedDocumentGenerator...")
    orch_gen = OrchestratedDocumentGenerator(output_dir)
    orch_file = orch_gen.generate_from_context(test_data["context"])
    print(f"   ✅ Generated: {orch_file}")
    generated_files.append(orch_file)
    
    # Test 5: Comprehensive Generator
    print("\n5. Testing ComprehensiveDocumentGenerator...")
    comp_gen = ComprehensiveDocumentGenerator(output_dir)
    comp_file = comp_gen.generate_from_context(test_data["context"])
    print(f"   ✅ Generated: {comp_file}")
    generated_files.append(comp_file)
    
    # Generer oppsummering
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"\n✅ Successfully generated {len(generated_files)} documents:")
    for f in generated_files:
        print(f"   - {Path(f).name}")
    
    print(f"\n📁 All documents saved to: {output_dir}/")
    
    # Lag en README i output-mappen
    readme_content = f"""# Test Documents Generated

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Documents Created:

1. **Oslomodell Assessment** - Full seriøsitetskrav assessment
2. **Triage Assessment** - Risk classification (RED/YELLOW/GREEN)
3. **Environmental Assessment** - Climate and environmental requirements
4. **Orchestrated Assessment** - Combined assessment from all agents
5. **Comprehensive Assessment** - Full ComprehensiveAssessment model

## Test Procurement:
- **Name:** {test_data['procurement']['name']}
- **Value:** {test_data['procurement']['value']:,} NOK
- **Category:** {test_data['procurement']['category']}

## Results:
- **Triage:** {test_data['triage']['color']}
- **Crime Risk:** {test_data['oslomodell']['vurdert_risiko_for_akrim']}
- **Environmental Risk:** {test_data['environmental']['environmental_risk_level']}
- **Total Requirements:** {len(test_data['oslomodell']['påkrevde_seriøsitetskrav'])}
"""
    
    readme_path = Path(output_dir) / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"\n📝 README created: {readme_path}")
    
    return generated_files

if __name__ == "__main__":
    # Kjør tester
    files = test_all_generators()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
    print("="*60)