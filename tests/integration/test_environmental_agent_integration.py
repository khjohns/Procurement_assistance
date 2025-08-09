# test_environmental_agent_integration.py - REFAKORERT VERSJON
"""
Integrasjonstest for EnvironmentalAgent med reell LLM, Embedding og RPC Gateway.
Tester den komplette flyten mot ekte tjenester for en realistisk vurdering.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Legg til rotmappen i systemstien for å finne kildekode
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.specialists.environmental_agent_refactored import EnvironmentalAgent
from src.models.procurement_models_refactored import (
    ProcurementRequest,
    ProcurementCategory,
    EnvironmentalAssessmentResult,
    TransportType,
    Requirement
)
from src.tools.enhanced_llm_gateway import LLMGateway
from src.tools.embedding_gateway import EmbeddingGateway

# Last miljøvariabler fra .env-fil
load_dotenv()

def print_rich_environmental_assessment(result: EnvironmentalAssessmentResult):
    """Skriver ut et EnvironmentalAssessmentResult-objekt på en leservennlig måte."""
    
    print(f"\n{'='*40}")
    print("VURDERINGSRESULTATER - MILJØKRAV")
    print(f"{'='*40}")

    # 1. Metadata
    print(f"\n📊 METADATA:")
    print(f"  Anskaffelses-ID: {result.procurement_id}")
    print(f"  Navn: {result.procurement_name}")
    print(f"  Vurderingsdato: {result.assessment_date}")
    print(f"  Vurdert av: {result.assessed_by}")
    print(f"  Konfidens: {result.confidence:.1%}")

    # 2. Overordnet miljøvurdering
    print(f"\n🌍 MILJØVURDERING:")
    print(f"  Samlet miljørisiko: {result.environmental_risk.value.upper()}")
    print(f"  Vurdert klimapåvirkning: {'Ja' if result.climate_impact_assessed else 'Nei'}")
    print(f"  Anbefaler markedsdialog: {'Ja' if result.market_dialogue_recommended else 'Nei'}")

    # 3. Transportkrav
    print(f"\n🚚 TRANSPORTKRAV ({len(result.transport_requirements)} totalt):")
    if not result.transport_requirements:
        print("  Ingen spesifikke transportkrav identifisert.")
    for i, req in enumerate(result.transport_requirements, 1):
        print(f"\n  Krav {i}:")
        print(f"    Type: {req.type.value}")
        print(f"    Krever nullutslipp: {'Ja' if req.zero_emission_required else 'Nei'}")
        print(f"    Biodrivstoff som alternativ: {'Ja' if req.biofuel_alternative else 'Nei'}")
        print(f"    Insentiv gjelder: {'Ja' if req.incentive_applicable else 'Nei'}")
        if req.deadline:
            print(f"    Frist: {req.deadline}")
            
    # 4. Anbefalte tildelingskriterier
    print(f"\n🏆 ANBEFALTE TILDELINGSKRITERIER:")
    if not result.award_criteria_recommended:
        print("  Ingen spesifikke tildelingskriterier anbefalt.")
    for criterion in result.award_criteria_recommended:
        print(f"  - {criterion}")

    # 5. Viktige frister
    print(f"\n🗓️ VIKTIGE FRISTER:")
    if not result.important_deadlines:
        print("  Ingen spesifikke frister identifisert.")
    for name, date in result.important_deadlines.items():
        print(f"  - {name.replace('_', ' ').capitalize()}: {date}")

    # 6. Dokumentasjonskrav og oppfølgingspunkter
    print(f"\n📋 DOKUMENTASJON OG OPPFØLGING:")
    print("  Krav til dokumentasjon:")
    for doc_req in result.documentation_requirements:
        print(f"    - {doc_req}")
    print("\n  Punkter for kontraktsoppfølging:")
    for point in result.follow_up_points:
        print(f"    - {point}")

    # 7. Anbefalinger
    print(f"\n💡 GENERELLE ANBEFALINGER:")
    for rec in result.recommendations:
        print(f"  - {rec}")
        
    # 8. Kontekst
    print(f"\n📚 KONTEKST BRUKT I VURDERING:")
    print(f"  Antall dokumenter brukt: {len(result.context_documents_used)}")
    for doc_id in result.context_documents_used[:5]:
        print(f"  - {doc_id}")
    if len(result.context_documents_used) > 5:
        print("  ...")


async def test_real_environmental_agent():
    """Tester EnvironmentalAgent mot reelle tjenester (LLM, Embedding, RPC)."""
    
    print("\n" + "="*80)
    print("🧪 TESTER REELL ENVIRONMENTAL AGENT (MED RPC/RAG)")
    print("="*80)

    # Initialiser reelle gateways
    llm_gateway = LLMGateway()
    embedding_gateway = EmbeddingGateway(api_key=os.getenv("GEMINI_API_KEY"))
    agent = EnvironmentalAgent(llm_gateway, embedding_gateway)
    
    # Lag en test-anskaffelse som er relevant for miljøkrav
    procurement = ProcurementRequest(
        name="Bygging av ny ungdomsskole med idrettshall",
        value=85_000_000,
        description="Totalentreprise for bygging av ny ungdomsskole med idrettshall, uteområder og parkeringsanlegg. Prosjektet inkluderer riving, grunnarbeid og betydelig massetransport.",
        category=ProcurementCategory.BYGGE,
        duration_months=24,
        includes_construction=True,
        involves_transport=True,
        transport_type=TransportType.MASSETRANSPORT,
        estimated_transport_volume=5000, # tonn
        involves_demolition=True,
        involves_earthworks=True,
        construction_site_size=15000 # m2
    )
    
    print("\n📋 Test-anskaffelse:")
    print(f"  Navn: {procurement.name}")
    print(f"  Verdi: {procurement.value:,} NOK")
    print(f"  Kategori: {procurement.category.value}")
    print(f"  Varighet: {procurement.duration_months} måneder")
    print(f"  Transporttype: {procurement.transport_type.value}")
    
    print(f"\n{'='*40}")
    print("KJØRER VURDERING...")
    print(f"{'='*40}\n")
    
    try:
        # Kjør agenten med reelle tjenester
        result_dict = await agent.execute({"procurement": procurement.model_dump()})
        
        # Valider resultatet mot Pydantic-modellen
        validated_result = EnvironmentalAssessmentResult.model_validate(result_dict)
        
        # Skriv ut det rike resultatet
        print_rich_environmental_assessment(validated_result)

        # Noen enkle sjekker for å verifisere innhold
        assert validated_result.environmental_risk in ["middels", "høy"]
        assert validated_result.market_dialogue_recommended is True
        assert len(validated_result.recommendations) > 0
        assert len(validated_result.context_documents_used) > 0 # Bevis på at RAG funket

        print("\n\n✅ Testen fullførte og validerte successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test feilet: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Kjører test-suiten."""
    print("\n" + "="*80)
    print("🚀 INTEGRASJONSTEST-SUITE FOR ENVIRONMENTAL AGENT")
    print("   Tester med reell LLM, Embedding og RAG via RPC")
    print("="*80)
    
    results = {}
    
    try:
        results['real_agent_test'] = await test_real_environmental_agent()
    except Exception as e:
        print(f"❌ Testen for reell agent feilet katastrofalt: {e}")
        results['real_agent_test'] = False
    
    # Oppsummering
    print("\n" + "="*80)
    print("📊 TESTOPPSUMMERING")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:25s}: {status}")
    
    if all(results.values()):
        print("\n🎉 ALLE TESTER BESTÅTT!")
        print("\nDemonstrerte forbedringer:")
        print("  ✅ Full end-to-end testing mot reelle tjenester.")
        print("  ✅ Dynamisk kunnskapsinnhenting (RAG) via RPC er verifisert.")
        print("  ✅ Strukturert, typesikker output validert mot Pydantic-modell.")
        print("  ✅ Informativ og leservennlig output i konsollen.")
    else:
        print("\n⚠️ Noen tester feilet. Sjekk loggen over for detaljer.")
    
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    print("\n📝 Merk: Denne testen krever reelle API-nøkler og en kjørende RPC-gateway.")
    print("   Sørg for at .env-filen er korrekt satt opp.")
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)