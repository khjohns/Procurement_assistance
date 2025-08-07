#!/usr/bin/env python3
"""
load_oslomodell_knowledge_rpc.py
Script to load Oslomodell knowledge base via RPC Gateway.
Run this after running the SQL setup script.
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

# Oslomodell knowledge base documents
OSLOMODELL_KNOWLEDGE_BASE = [
    {
        "id": "oslo-001",
        "content": """4. Anvendelsesområde for Oslomodellens seriøsitetskrav
4.1 I bygge-, anleggs- og tjenesteanskaffelser fra kr 100 000 til kr 500 000 skal krav A-E
alltid benyttes. Krav F-T skal benyttes ved risiko for arbeidslivskriminalitet og sosial
dumping.
4.2 I bygge-, anleggs- og renholdsanskaffelser over kr 500 000 skal krav A-U alltid
benyttes. Krav V skal benyttes alltid når vilkårene er oppfylt, jf. punkt 6.
4.3 I tjenesteanskaffelser over kr 500 000 skal krav A-H alltid benyttes. Krav I-T skal
benyttes ved risiko for arbeidslivskriminalitet eller sosial dumping. Krav V skal alltid
benyttes når vilkårene er oppfylt, jf. punkt 6.
5. Begrensninger i bruk av underleverandører i vertikal kjede
5.1 Ved kunngjøring av bygge-, anleggs- og tjenesteanskaffelser gjelder følgende adgang til
bruk av underleverandører, jf. krav H:
a) I anskaffelser der det foreligger risiko for arbeidslivskriminalitet og sosial
dumping kan det maksimalt tillates ett ledd underleverandører i vertikal kjede.
b) I anskaffelser der det foreligger høy risiko for arbeidslivskriminalitet eller sosial
dumping, kan det nektes bruk av underleverandører.
c) I anskaffelser der det foreligger lav risiko for arbeidslivskriminalitet og sosial
dumping, kan det åpnes for to ledd underleverandører i vertikal kjede.
6. Krav til bruk av lærlinger
I anskaffelser over statlig terskelverdi for bruk av lærlinger, med varighet over tre måneder og
innenfor utførende fagområder med særlig behov for læreplasser, skal det stilles krav til bruk
av lærlinger, jf. krav V.""",
        "metadata": {
            "tema": "Seriøsitetskrav",
            "kilde": "Instruks for Oslo kommunes anskaffelser",
            "relevante_krav": ["A-E", "F-T", "A-H", "A-U", "I-T", "V"],
            "punkter": ["4", "5", "6"],
            "nøkkelord": ["seriøsitetskrav", "underleverandører", "lærlinger", "arbeidslivskriminalitet"]
        }
    },
    {
        "id": "oslo-002",
        "content": """7 Oslomodellens krav til aktsomhetsvurderinger for ansvarlig næringsliv
7.1 I alle anskaffelser skal det foretas en vurdering av risiko for brudd på grunnleggende
menneskerettigheter, arbeidstakerrettigheter og internasjonal humanitærrett,
miljøødeleggelse eller korrupsjon i leverandørkjeden.
7.2 Oslo kommune skal ikke handle med leverandører hvis aktiviteter kan knyttes til
alvorlige brudd på grunnleggende menneskerettigheter, arbeidstakerrettigheter eller
internasjonal humanitærrett, eller alvorlige miljøødeleggelser eller korrupsjon.
7.3 Kravsett A, Alminnelige krav til aktsomhetsvurderinger for ansvarlig næringsliv
benyttes i anskaffelser av varer, tjenester, bygg og anlegg over kr 500 000, der det er
høy risiko, jf. punkt 7.1.
7.4 Kravsett B, Forenklede krav til aktsomhetsvurderinger for ansvarlig næringsliv kan
benyttes i anskaffelser av varer, tjenester, bygg og anlegg over kr 500 000, der det er
høy risiko, jf. punkt 7.1, istedenfor kravsett A.
7.5 Dersom vilkårene for bruk av kravsett B er oppfylt, skal virksomhetene dokumentere
vurderingen i kontraktsstrategien.
7.6 Virksomhetene kan benytte strengere kvalifikasjons- eller kontraktskrav enn det som er
pålagt der dette er hensiktsmessig.""",
        "metadata": {
            "tema": "Aktsomhetsvurderinger",
            "kilde": "Instruks for Oslo kommunes anskaffelser",
            "relevante_krav": ["Kravsett A", "Kravsett B"],
            "punkter": ["7"],
            "nøkkelord": ["aktsomhetsvurderinger", "menneskerettigheter", "ansvarlig næringsliv", "korrupsjon"]
        }
    },
    {
        "id": "oslo-003",
        "content": """Statlig terskelverdi for lærlinger
Terskelverdi for når det skal stilles krav om bruk av lærlinger er kr 1,3 millioner ekskl. mva
for statlige myndigheter. Oslo kommune følger statens terskelverdi.
Utførende fagområder med særlig behov for læreplasser inkluderer:
- Tømrerfaget
- Rørleggerfaget  
- Elektrofag
- Betongfaget
- Malerfaget
- Murerfaget
- Anleggsfaget
- Ventilasjonfaget
Kravet gjelder kontrakter med varighet over 3 måneder.""",
        "metadata": {
            "tema": "Lærlinger",
            "kilde": "Instruks for Oslo kommunes anskaffelser",
            "relevante_krav": ["V"],
            "punkter": ["6"],
            "nøkkelord": ["lærlinger", "terskelverdi", "fagområder", "læreplasser"]
        }
    }
]

async def load_knowledge_base():
    """Load Oslomodell knowledge into database via RPC Gateway."""
    load_dotenv()
    
    # Check environment
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY not found in .env file")
        return False
    
    gateway_url = os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
    
    # Initialize components
    embedding_gateway = EmbeddingGateway(api_key=gemini_api_key)
    
    logger.info(f"Loading {len(OSLOMODELL_KNOWLEDGE_BASE)} documents into knowledge base")
    
    async with RPCGatewayClient(
        agent_id="knowledge_ingester",
        gateway_url=gateway_url
    ) as rpc_client:
        
        success_count = 0
        
        for doc in OSLOMODELL_KNOWLEDGE_BASE:
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
                result = await rpc_client.call("database.store_knowledge_document", {
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
        
        logger.info(f"Loaded {success_count}/{len(OSLOMODELL_KNOWLEDGE_BASE)} documents")
        
        # Verify by searching
        logger.info("Verifying knowledge base with test search...")
        
        test_query = "seriøsitetskrav bygge anlegg over 500000"
        query_embedding = await embedding_gateway.create_embedding(
            text=test_query,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=1536
        )
        
        search_result = await rpc_client.call("database.search_knowledge_documents", {
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
        
        return success_count == len(OSLOMODELL_KNOWLEDGE_BASE)

async def load_from_csv(csv_path: str):
    """
    Alternative: Load from CSV file.
    CSV format: id,content,tema,kilde,relevante_krav,punkter,nøkkelord
    """
    import pandas as pd
    from src.tools.knowledge_ingester_rpc import KnowledgeIngesterRPC
    
    load_dotenv()
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY not found")
        return
    
    embedding_gateway = EmbeddingGateway(api_key=gemini_api_key)
    ingester = KnowledgeIngesterRPC(embedding_gateway)
    
    await ingester.ingest_from_csv(csv_path)

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load Oslomodell knowledge base")
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
    
    print("🚀 Oslomodell Knowledge Base Loader (RPC Gateway)")
    print("="*60)
    
    if args.csv:
        print(f"Loading from CSV: {args.csv}")
        await load_from_csv(args.csv)
    else:
        print("Loading hardcoded knowledge base...")
        success = await load_knowledge_base()
        
        if success:
            print("\n✅ Knowledge base loaded successfully!")
        else:
            print("\n❌ Some documents failed to load")
            sys.exit(1)
    
    print("="*60)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())