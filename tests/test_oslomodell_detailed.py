#!/usr/bin/env python3
"""
test_oslomodell_detailed.py
Grundig test av Oslomodell-agentens vurderinger mot faktiske instrukskrav.
Tester direkte uten orchestrator for å isolere agentens logikk.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, List
import json
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.enhanced_llm_gateway import LLMGateway
from src.tools.embedding_gateway import EmbeddingGateway
from src.specialists.oslomodell_agent import OslomodellAgent
from src.models.procurement_models import ProcurementCategory

load_dotenv()

# Definisjon av korrekte krav basert på Instruksen
INSTRUKS_KRAV = {
    "bygge_anlegg_under_500k": {
        "seriøsitetskrav": ["A", "B", "C", "D", "E"],  # Alltid
        "ekstra_ved_risiko": ["F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
        "beskrivelse": "Bygge/anlegg 100k-500k"
    },
    "bygge_anlegg_over_500k": {
        "seriøsitetskrav": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"],  # A-U alltid
        "beskrivelse": "Bygge/anlegg/renhold over 500k"
    },
    "tjeneste_under_500k": {
        "seriøsitetskrav": ["A", "B", "C", "D", "E"],  # Alltid
        "ekstra_ved_risiko": ["F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
        "beskrivelse": "Tjeneste 100k-500k"
    },
    "tjeneste_over_500k": {
        "seriøsitetskrav": ["A", "B", "C", "D", "E", "F", "G", "H"],  # A-H alltid
        "ekstra_ved_risiko": ["I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],  # I-T ved risiko
        "beskrivelse": "Tjeneste over 500k"
    }
}

# Test cases basert på faktiske scenarier
TEST_CASES = [
    {
        "name": "Små kontorrekvisita",
        "value": 250_000,
        "category": "vare",
        "duration_months": 12,
        "description": "Årlig avtale for kontorrekvisita",
        "expected": {
            "risk": "lav",
            "krav_count": 5,  # A-E
            "krav_codes": ["A", "B", "C", "D", "E"],
            "underleverandør": 2,  # Lav risiko = 2 ledd
            "lærlinger": False  # Under 1.3M
        }
    },
    {
        "name": "Bygge barnehage lav verdi",
        "value": 450_000,
        "category": "bygge",
        "duration_months": 3,
        "description": "Mindre ombygging av eksisterende barnehage",
        "expected": {
            "risk": "lav",
            "krav_count": 5,  # A-E (under 500k)
            "krav_codes": ["A", "B", "C", "D", "E"],
            "underleverandør": 2,
            "lærlinger": False  # Under 1.3M
        }
    },
    {
        "name": "Renhold kommune",
        "value": 800_000,
        "category": "renhold",
        "duration_months": 24,
        "description": "Renhold av kommunale bygg",
        "expected": {
            "risk": "moderat",  # Renhold har ofte risiko
            "krav_count": 21,  # A-U for renhold over 500k
            "krav_codes": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"],
            "underleverandør": 1,  # Moderat risiko
            "lærlinger": False  # Under 1.3M
        }
    },
    {
        "name": "Stor byggeentreprise",
        "value": 35_000_000,
        "category": "bygge",
        "duration_months": 18,
        "description": "Totalentreprise ny skole med idrettshall",
        "expected": {
            "risk": "høy",
            "krav_count": 21,  # A-U
            "krav_codes": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"],
            "underleverandør": 1,  # Høy risiko = maks 1 ledd
            "lærlinger": True,  # Over 1.3M + bygge
            "krav_v": True  # Krav V om lærlinger
        }
    },
    {
        "name": "IT-konsulenter",
        "value": 2_500_000,
        "category": "konsulent",
        "duration_months": 24,
        "description": "Konsulenter for systemutvikling",
        "expected": {
            "risk": "lav",  # IT har vanligvis lav risiko for arbeidslivskrim
            "krav_count": 8,  # A-H for tjeneste over 500k
            "krav_codes": ["A", "B", "C", "D", "E", "F", "G", "H"],
            "underleverandør": 2,  # Lav risiko
            "lærlinger": False  # Ikke utførende fag
        }
    },
    {
        "name": "Vaktmestertjenester",
        "value": 1_500_000,
        "category": "tjeneste",
        "duration_months": 36,
        "description": "Vaktmestertjenester for kommunale bygg",
        "expected": {
            "risk": "moderat",  # Risiko for sosial dumping
            "krav_count": 20,  # A-H + I-T ved risiko
            "krav_codes": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
            "underleverandør": 1,
            "lærlinger": False  # Ikke spesifikt utførende fag
        }
    },
    {
        "name": "Anleggsarbeid vei",
        "value": 12_000_000,
        "category": "anlegg",
        "duration_months": 6,
        "description": "Asfaltering og veiarbeid",
        "expected": {
            "risk": "høy",
            "krav_count": 21,  # A-U for anlegg over 500k
            "krav_codes": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"],
            "underleverandør": 1,
            "lærlinger": True,  # Over 1.3M + anleggsfaget
            "krav_v": True
        }
    }
]

async def test_single_case(agent: OslomodellAgent, test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Test en enkelt case og returner detaljert analyse."""
    
    print(f"\n{'='*60}")
    print(f"Testing: {test_case['name']}")
    print(f"Verdi: {test_case['value']:,} NOK | Kategori: {test_case['category']} | Varighet: {test_case['duration_months']} mnd")
    print("-"*60)
    
    # Execute agent
    result = await agent.execute({
        "procurement": {
            "name": test_case["name"],
            "value": test_case["value"],
            "category": test_case["category"],
            "duration_months": test_case["duration_months"],
            "description": test_case["description"]
        }
    })
    
    # Analyze results
    analysis = {
        "case": test_case["name"],
        "passed": True,
        "details": {},
        "errors": []
    }
    
    # 1. Check risk assessment
    actual_risk = result.get("vurdert_risiko_for_akrim", "").lower()
    expected_risk = test_case["expected"]["risk"]
    
    print(f"\n📊 Risikovurdering:")
    print(f"   Forventet: {expected_risk}")
    print(f"   Faktisk: {actual_risk}")
    
    if actual_risk != expected_risk:
        analysis["errors"].append(f"Feil risiko: {actual_risk} (forventet {expected_risk})")
        analysis["passed"] = False
        print(f"   ❌ FEIL")
    else:
        print(f"   ✅ Korrekt")
    
    # 2. Check requirements (seriøsitetskrav)
    actual_krav = result.get("påkrevde_seriøsitetskrav", [])
    expected_krav = test_case["expected"]["krav_codes"]
    
    print(f"\n📋 Seriøsitetskrav:")
    print(f"   Forventet: {expected_krav} ({len(expected_krav)} krav)")
    print(f"   Faktisk: {actual_krav} ({len(actual_krav)} krav)")
    
    if set(actual_krav) != set(expected_krav):
        missing = set(expected_krav) - set(actual_krav)
        extra = set(actual_krav) - set(expected_krav)
        
        if missing:
            analysis["errors"].append(f"Mangler krav: {sorted(missing)}")
        if extra:
            analysis["errors"].append(f"Ekstra krav: {sorted(extra)}")
        
        analysis["passed"] = False
        print(f"   ❌ FEIL - Antall: {len(actual_krav)} vs {len(expected_krav)}")
        if missing:
            print(f"      Mangler: {sorted(missing)}")
        if extra:
            print(f"      For mye: {sorted(extra)}")
    else:
        print(f"   ✅ Korrekt")
    
    # 3. Check subcontractor levels
    actual_underlev = result.get("anbefalt_antall_underleverandørledd", -1)
    expected_underlev = test_case["expected"]["underleverandør"]
    
    print(f"\n🔗 Underleverandørledd:")
    print(f"   Forventet: {expected_underlev}")
    print(f"   Faktisk: {actual_underlev}")
    
    if actual_underlev != expected_underlev:
        analysis["errors"].append(f"Feil underleverandørledd: {actual_underlev} (forventet {expected_underlev})")
        analysis["passed"] = False
        print(f"   ❌ FEIL")
    else:
        print(f"   ✅ Korrekt")
    
    # 4. Check apprentice requirements
    actual_lærling = result.get("krav_om_lærlinger", {}).get("status", False)
    expected_lærling = test_case["expected"]["lærlinger"]
    
    print(f"\n👷 Lærlingkrav:")
    print(f"   Forventet: {'Ja' if expected_lærling else 'Nei'}")
    print(f"   Faktisk: {'Ja' if actual_lærling else 'Nei'}")
    print(f"   Begrunnelse: {result.get('krav_om_lærlinger', {}).get('begrunnelse', 'Ingen')}")
    
    if actual_lærling != expected_lærling:
        analysis["errors"].append(f"Feil lærlingkrav: {actual_lærling} (forventet {expected_lærling})")
        analysis["passed"] = False
        print(f"   ❌ FEIL")
    else:
        print(f"   ✅ Korrekt")
    
    # 5. Check if Krav V is mentioned when relevant
    if test_case["expected"].get("krav_v"):
        has_v = "V" in actual_krav
        print(f"\n📌 Krav V (lærlinger):")
        print(f"   {'✅ Inkludert' if has_v else '❌ Mangler'}")
        
        if not has_v:
            analysis["errors"].append("Mangler krav V for lærlinger")
            analysis["passed"] = False
    
    # 6. Display recommendations
    recommendations = result.get("recommendations", [])
    if recommendations:
        print(f"\n💡 Anbefalinger fra agent:")
        for rec in recommendations[:3]:
            print(f"   • {rec}")
    
    # 7. Context retrieved
    print(f"\n📚 Kontekst hentet:")
    print(f"   Confidence: {result.get('confidence', 0):.0%}")
    
    # Summary for this case
    print(f"\n{'='*60}")
    if analysis["passed"]:
        print(f"✅ {test_case['name']}: BESTÅTT")
    else:
        print(f"❌ {test_case['name']}: FEILET")
        for error in analysis["errors"]:
            print(f"   - {error}")
    
    analysis["result"] = result
    return analysis

async def main():
    """Run comprehensive Oslomodell tests."""
    
    print("\n" + "="*80)
    print("🏛️  GRUNDIG TEST AV OSLOMODELL-AGENT")
    print("="*80)
    print("\nDenne testen verifiserer at Oslomodell-agenten følger instruksen korrekt.")
    print("Tester direkte mot agenten uten orchestrator for å isolere logikken.")
    
    # Initialize agent
    llm_gateway = LLMGateway()
    embedding_gateway = EmbeddingGateway(api_key=os.getenv("GEMINI_API_KEY"))
    agent = OslomodellAgent(llm_gateway, embedding_gateway)
    
    # Run all test cases
    results = []
    passed_count = 0
    
    for test_case in TEST_CASES:
        try:
            analysis = await test_single_case(agent, test_case)
            results.append(analysis)
            if analysis["passed"]:
                passed_count += 1
        except Exception as e:
            print(f"\n❌ Exception for {test_case['name']}: {e}")
            results.append({
                "case": test_case["name"],
                "passed": False,
                "errors": [f"Exception: {str(e)}"]
            })
    
    # Final summary
    print("\n" + "="*80)
    print("📊 SLUTTRESULTAT")
    print("="*80)
    
    print(f"\nTestet {len(TEST_CASES)} scenarier")
    print(f"✅ Bestått: {passed_count}")
    print(f"❌ Feilet: {len(TEST_CASES) - passed_count}")
    
    # Detailed error summary
    print("\n🔍 Detaljert feiloversikt:")
    for result in results:
        if not result["passed"]:
            print(f"\n{result['case']}:")
            for error in result["errors"]:
                print(f"   • {error}")
    
    # Common patterns
    print("\n📈 Vanlige mønstre:")
    krav_errors = [r for r in results if any("krav" in e.lower() for e in r.get("errors", []))]
    risk_errors = [r for r in results if any("risiko" in e.lower() for e in r.get("errors", []))]
    
    if krav_errors:
        print(f"   • Feil i seriøsitetskrav: {len(krav_errors)} tilfeller")
    if risk_errors:
        print(f"   • Feil i risikovurdering: {len(risk_errors)} tilfeller")
    
    # Save detailed results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"oslomodell_test_results_{timestamp}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "summary": {
                "total": len(TEST_CASES),
                "passed": passed_count,
                "failed": len(TEST_CASES) - passed_count
            },
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detaljerte resultater lagret til: {filename}")
    
    # Return exit code
    return 0 if passed_count == len(TEST_CASES) else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)