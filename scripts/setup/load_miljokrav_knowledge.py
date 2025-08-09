#!/usr/bin/env python3
"""
load_miljokrav_knowledge.py
Script to load Miljøkrav knowledge base via RPC Gateway.
Chunks the climate and environment requirements instruction.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import structlog

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.embedding_gateway import EmbeddingGateway
from src.tools.rpc_gateway_client import RPCGatewayClient

logger = structlog.get_logger()

# Miljøkrav knowledge base documents - chunked from the instruction
MILJOKRAV_KNOWLEDGE_BASE = [
    {
        "id": "miljokrav-001",
        "content": """1. Formål og 2. Virkeområde
Instruksen gir føringer for kommunens virksomheter for bruk og oppfølging av klima- og miljøkrav i planlegging, bestilling, anskaffelse og kontraktsoppfølging knyttet til bygg og anlegg. Instruksen skal sikre en effektiv og enhetlig bruk av krav og føringer, øke sannsynligheten for vellykket gjennomføring av utslippsfrie bygge- og anleggsanskaffelser, og bidra til raskere omstilling til mer sirkulære og klimavennlige løsninger for bygg og anlegg.

Denne instruksen gjelder for alle bygge- og anleggsanskaffelser med en verdi over kr 100 000 som gjennomføres av virksomheter som er en del av rettssubjektet Oslo kommune.""",
        "metadata": {
            "tema": "Formål og virkeområde",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["1", "2"],
            "nøkkelord": ["formål", "virkeområde", "100000", "bygge", "anlegg"],
            "terskelverdi": 100000
        }
    },
    {
        "id": "miljokrav-002",
        "content": """3. Planlegging og markedsdialog
3.1. Virksomhetene skal sette av tilstrekkelig tid til å legge til rette for utslippsfrie løsninger, fra tidlig fase med utredning til oppstart og gjennomføring av prosjekter.
3.2. Virksomhetene skal gjennomføre jevnlige undersøkelser i markedet om tilgjengelige utslippsfrie maskiner og kjøretøy for egne prosjekter og formål.
3.3. Virksomhetene skal i tillegg legge til grunn felles kunnskap om markedet som gjøres tilgjengelig i regi av Utviklings- og kompetanseetaten (UKE).
3.4. Virksomhetene skal gjøre nødvendige kartlegginger og avklaringer med nettselskap eller eventuelt andre relevante aktører om tilgjengelige løsninger for energi og effekt i forkant av sine anskaffelser.""",
        "metadata": {
            "tema": "Planlegging og markedsdialog",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["3"],
            "nøkkelord": ["planlegging", "markedsdialog", "utslippsfrie løsninger", "UKE"]
        }
    },
    {
        "id": "miljokrav-003",
        "content": """4. Bruk av Oslo kommunes standard klima- og miljøkrav
4.1. Virksomhetene skal bruke Oslo kommunes standard klima- og miljøkrav i alle bygge- og anleggsanskaffelser med verdi over kr 100 000, med mindre unntak som fremgår av punkt 7 kommer til anvendelse.
4.2. Virksomhetene må i den enkelte anskaffelse vurdere om vilkårene i anskaffelsesforskriften § 7-9 fjerde ledd og unntak fra hovedregelen i § 7-9 andre ledd, er oppfylt. Vurderingene skal begrunnes i anskaffelsesdokumentene. Dersom Oslo kommunes standard klima- og miljøkrav stilles som kontraktskrav skal det henvises til disse i kravspesifikasjonen.""",
        "metadata": {
            "tema": "Standard klima- og miljøkrav",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["4"],
            "nøkkelord": ["standard", "klima", "miljøkrav", "100000", "kravspesifikasjon"],
            "terskelverdi": 100000,
            "lovhenvisning": "anskaffelsesforskriften § 7-9"
        }
    },
    {
        "id": "miljokrav-004",
        "content": """5. Premiering av utslippsfri massetransport
Virksomhetene skal premiere andel utslippsfri massetransport. Virksomhetene kan velge mellom å premiere ved å bruke bonus, som stilles som kontraktskrav, eller ved å bruke tildelingskriterier i konkurransen. Premiering av utslippsfri massetransport avsluttes innen 1.1.2030.""",
        "metadata": {
            "tema": "Utslippsfri massetransport",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["5"],
            "nøkkelord": ["massetransport", "utslippsfri", "bonus", "tildelingskriterier"],
            "frist": "2030-01-01"
        }
    },
    {
        "id": "miljokrav-005",
        "content": """6. Premiering av utslippsfri og biogassbaserte kjøretøy for øvrig transport over 3,5 tonn
Virksomhetene skal, i tillegg til å bruke kontraktskrav III, bruke tildelingskriterier for å premiere andel utslippsfrie eller biogassbaserte kjøretøy over 3,5 tonn. Virksomhetene skal gi utslippsfrie kjøretøy høyere uttelling enn biogassbaserte kjøretøy. Premiering av utslippsfrie eller biogassbaserte kjøretøy avsluttes innen 1.1.2027. Tildelingskriterier skal imidlertid fortsatt benyttes etter 1.1.2027 i anskaffelser der det fastsettes en senere dato for når kontraktskravet inntrer, jf. punkt 7.2.""",
        "metadata": {
            "tema": "Kjøretøy over 3,5 tonn",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["6"],
            "nøkkelord": ["kjøretøy", "3.5 tonn", "utslippsfri", "biogass", "tildelingskriterier"],
            "vektgrense": 3500,
            "frist": "2027-01-01"
        }
    },
    {
        "id": "miljokrav-006",
        "content": """7. Unntak fra Oslo kommunes standard klima- og miljøkrav (del 1)
7.1. Virksomhetene kan gi unntak fra klima- og miljøkravet for maskiner og kjøretøy, jf. punkt 4.1., der det ikke er praktisk mulig eller hensiktsmessig av hensyn til tilstrekkelig konkurranse å stille klima- og miljøkrav. Unntak fra klima- og miljøkrav skal brukes restriktivt. Unntaket skal tas inn i anskaffelsesdokumentene.
7.2. Der det ikke er praktisk mulig av hensyn til tilgjengeligheten i markedet å stille krav om at kjøretøy over 3,5 tonn til øvrig transport skal være utslippsfrie eller biogassbaserte fra 1.1.2027, kan virksomhetene i konkurransefasen fastsette en senere dato for når kravet inntrer. Virksomhetene skal ikke fastsette en senere dato enn nødvendig ut ifra markedssituasjonen.""",
        "metadata": {
            "tema": "Unntak",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["7.1", "7.2"],
            "nøkkelord": ["unntak", "praktisk mulig", "konkurranse", "markedssituasjon"],
            "frist": "2027-01-01"
        }
    },
    {
        "id": "miljokrav-007",
        "content": """7. Unntak fra Oslo kommunes standard klima- og miljøkrav (del 2)
7.3. Der virksomhetene gir unntak fra klima- og miljøkrav, jf. punkt 7.1. og 7.2., skal virksomhetene vurdere insentiver til omstilling i form av tildelingskriterier eller liknende i konkurransen, jf. blant annet punkt 6.
7.4. Der det ikke kan stilles standard klima- og miljøkrav til bygge- og anleggsarbeid og/eller transport skal det som minimum stilles krav om bærekraftig biodrivstoff ut over omsetningskrav.
7.5. Der virksomhetene gir unntak fra standard klima- og miljøkrav, jf. punkt 7.1. og 7.2, må de sikre at anskaffelsen likevel gjøres i tråd med forskrift om offentlige anskaffelser § 7-9. Vurderingene skal dokumenteres i anskaffelsesdokumentene.
7.6. Vurderingene etter punkt 7.1. – 7.5. skal dokumenteres i kontraktsstrategien.""",
        "metadata": {
            "tema": "Unntak og minimumskrav",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["7.3", "7.4", "7.5", "7.6"],
            "nøkkelord": ["insentiver", "biodrivstoff", "dokumentasjon", "kontraktsstrategi"],
            "lovhenvisning": "anskaffelsesforskriften § 7-9"
        }
    },
    {
        "id": "miljokrav-008",
        "content": """7. Unntak fra Oslo kommunes standard klima- og miljøkrav (del 3)
7.7. Etter at kontrakt er inngått, kan virksomhetene etter en konkret vurdering gi Leverandøren unntak fra klima- og miljøkrav til maskiner eller kjøretøy. Unntak kan ikke gis der behovet skyldes forhold Leverandøren kjente til eller burde ha kjent til ved innlevering av endelig tilbud. Virksomhetene skal godkjenne søknaden skriftlig.
7.8. Virksomhetene skal ha oversikt over unntak fra klima- og miljøkravene som gis.""",
        "metadata": {
            "tema": "Unntak etter kontraktsinngåelse",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["7.7", "7.8"],
            "nøkkelord": ["unntak", "leverandør", "kontrakt", "oversikt"]
        }
    },
    {
        "id": "miljokrav-009",
        "content": """8. Oppfølging og sanksjonering
8.1. Virksomhetene skal iverksette nødvendige tiltak for å styrke oppfølgingen av klima- og miljøkrav.
8.2. Virksomhetene skal følge opp og sanksjonere brudd på kontraktenes klima- og miljøkrav.
8.3. Virksomhetene kan, etter en konkret vurdering, fastsette en annen begrensning for leverandørens samlede gebyransvar enn det som følger av standardkravene.""",
        "metadata": {
            "tema": "Oppfølging og sanksjonering",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["8"],
            "nøkkelord": ["oppfølging", "sanksjonering", "brudd", "gebyr"]
        }
    },
    {
        "id": "miljokrav-010",
        "content": """9. Veiledning og 10. Rapportering
9.1. UKE utarbeider og forvalter veiledning til klima- og miljøkravene.
9.2. Virksomhetene skal legge veiledningen til grunn så langt den passer.

10. Rapportering
Virksomhetene skal benytte kommunens digitale system for oppfølging og rapportering av forbruk og utslipp fra kommunens bygge- og anleggsplasser. Data som innhentes i systemet skal benyttes til årsrapportering på klima og miljø, og klimabudsjettet.""",
        "metadata": {
            "tema": "Veiledning og rapportering",
            "kilde": "Instruks om bruk av klima- og miljøkrav",
            "punkter": ["9", "10"],
            "nøkkelord": ["veiledning", "UKE", "rapportering", "klimabudsjett", "digitalt system"]
        }
    }
]

async def load_knowledge_base():
    """Load Miljøkrav knowledge into database via RPC Gateway."""
    load_dotenv()
    
    # Check environment
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY not found in .env file")
        return False
    
    gateway_url = os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
    
    # Initialize components
    embedding_gateway = EmbeddingGateway(api_key=gemini_api_key)
    
    logger.info(f"Loading {len(MILJOKRAV_KNOWLEDGE_BASE)} documents into miljøkrav knowledge base")
    
    async with RPCGatewayClient(
        agent_id="knowledge_ingester",
        gateway_url=gateway_url
    ) as rpc_client:
        
        success_count = 0
        
        for doc in MILJOKRAV_KNOWLEDGE_BASE:
            try:
                logger.info(f"Processing document: {doc['id']}")
                
                # Generate embedding
                embedding = await embedding_gateway.create_embedding(
                    text=doc['content'],
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=1536
                )
                
                logger.debug(f"Generated embedding with dimension: {len(embedding)}")
                
                # Store via RPC
                result = await rpc_client.call("database.store_miljokrav_document", {
                    "documentId": doc['id'],
                    "content": doc['content'],
                    "embedding": embedding,
                    "metadata": doc['metadata']
                })
                
                if result.get('status') == 'success':
                    logger.info(f"✅ Successfully stored document {doc['id']}")
                    success_count += 1
                else:
                    logger.error(f"Failed to store document {doc['id']}", 
                               error=result.get('message'))
                    
            except Exception as e:
                logger.error(f"Error processing document {doc['id']}", 
                           error=str(e), exc_info=True)
        
        logger.info(f"Loaded {success_count}/{len(MILJOKRAV_KNOWLEDGE_BASE)} documents")
        
        # Verify by searching
        logger.info("Verifying knowledge base with test search...")
        
        test_query = "standard klima miljøkrav bygge anlegg over 100000"
        query_embedding = await embedding_gateway.create_embedding(
            text=test_query,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=1536
        )
        
        search_result = await rpc_client.call("database.search_miljokrav_documents", {
            "queryEmbedding": query_embedding,
            "threshold": 0.5,
            "limit": 5,
            "metadataFilter": {}
        })
        
        if search_result.get('status') == 'success':
            results = search_result.get('results', [])
            logger.info(f"Search test returned {len(results)} results")
            for r in results:
                logger.info(f"  - {r['documentId']}: similarity={r['similarity']:.3f}")
        else:
            logger.error("Search test failed", error=search_result.get('message'))
        
        return success_count == len(MILJOKRAV_KNOWLEDGE_BASE)

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load Miljøkrav knowledge base")
    parser.add_argument("--csv", help="Load from CSV file instead of hardcoded data")
    args = parser.parse_args()
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )
    
    print("🌱 Miljøkrav Knowledge Base Loader (RPC Gateway)")
    print("="*60)
    
    if args.csv:
        print(f"Loading from CSV: {args.csv}")
        # Future: implement CSV loading
        print("CSV loading not yet implemented")
    else:
        print("Loading hardcoded knowledge base...")
        success = await load_knowledge_base()
        
        if success:
            print("\n✅ Miljøkrav knowledge base loaded successfully!")
        else:
            print("\n❌ Some documents failed to load")
            sys.exit(1)
    
    print("="*60)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())