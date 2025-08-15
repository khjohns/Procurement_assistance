#!/usr/bin/env python3
"""
knowledge_ingester.py
Script to embed and upload enhanced Oslomodell knowledge chunks
via RPC Gateway, reading from a processed CSV file.
"""
import asyncio
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import structlog
from typing import Dict, Any, List

# Legg til prosjekt-roten i path for å finne src-mappen
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.embedding_gateway import EmbeddingGateway
from src.tools.rpc_gateway_client import RPCGatewayClient

logger = structlog.get_logger()

class KnowledgeIngester:
    """
    Håndterer embedding og opplasting av beriket kunnskap til databasen.
    """
    def __init__(self, embedding_gateway: EmbeddingGateway, rpc_gateway_client: RPCGatewayClient):
        self.embedding_gateway = embedding_gateway
        self.rpc_client = rpc_gateway_client

    async def ingest_csv(self, filepath: str):
        """
        Leser en CSV-fil, genererer embeddings, og laster dataen inn i databasen.
        Forventer at CSV-filen har kolonner 'status' og 'llmOutputJson'.
        """
        try:
            df = pd.read_csv(filepath, sep='|', quotechar='"')
            logger.info(f"Lastet CSV-filen '{filepath}' med {len(df)} rader.")
        except FileNotFoundError:
            logger.error(f"FEIL: Finner ikke filen '{filepath}'. Avslutter.")
            return

        # Bruk hele DataFrame for å prosessere alle rader
        approved_df = df.copy() # Changed: Removed filtering
        
        if approved_df.empty:
            logger.warning("Ingen rader funnet å prosessere.")
            return

        logger.info(f"Fant {len(approved_df)} rader for innlasting i databasen.")
        success_count = 0

        for index, row in approved_df.iterrows():
            chunk_id_for_log = row.get('chunk_id', 'ukjent-id')
            logger.info(f"Prosesserer chunk: {chunk_id_for_log}")
            
            try:
                # 1. Parse JSON-metadata
                chunk_metadata = json.loads(row['llm_output_json'])

                # Overstyr chunk_id med den fra CSV-kolonnen for å være sikker
                chunk_metadata['chunk_id'] = row['chunk_id']

                # 2. Lag tekst for embedding
                text_to_embed = self._create_text_for_embedding(chunk_metadata)
                
                # 3. Generer embedding
                embedding_vector = await self.embedding_gateway.create_embedding(
                    text=text_to_embed,
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=1536
                )

                # 4. Bygg en korrekt RPC-nyttelast som ett enkelt JSON-objekt
                #    Nøkkelen 'p_input_data' MÅ matche navnet på SQL-funksjonens parameter
                rpc_payload = {
                    "chunk_data": chunk_metadata,
                    "embedding": embedding_vector
                }

                # 5. Last opp til databasen
                response = await self.rpc_client.call(
                    "knowledge_base.store_enhanced_chunk",
                    rpc_payload
                )

                if response and response.get('status') == 'success':
                    uploaded_id = response.get('chunkId', chunk_id_for_log)
                    logger.info(f"✅ Vellykket! Chunk '{uploaded_id}' ble lastet opp.")
                    success_count += 1
                else:
                    logger.error(f"❌ FEIL under opplasting av chunk {chunk_id_for_log}", error=response.get('message'))

            except json.JSONDecodeError:
                logger.error(f"FEIL: Kunne ikke parse JSON for chunk {chunk_id_for_log}.")
            except Exception as e:
                logger.error(f"En uventet feil oppstod for chunk {chunk_id_for_log}", error=str(e), exc_info=True)
        
        logger.info(f"Fullført. {success_count}/{len(approved_df)} chunks ble lastet opp.")

    def _create_text_for_embedding(self, metadata: Dict[str, Any]) -> str:
        """
        Kombinerer de viktigste tekstfeltene for å skape en semantisk rik
        tekst for embedding.
        """
        title = metadata.get('title', '')
        summary = metadata.get('summary', '')
        keywords = ", ".join(metadata.get('keywords', []))
        
        return f"Tittel: {title}\nSammendrag: {summary}\nNøkkelord: {keywords}"


async def main():
    """Hovedfunksjon for å kjøre skriptet."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Embed and load Oslomodell knowledge from a processed CSV file.")
    parser.add_argument("csv_file", help="Path to the CSV file with processed and QA'd chunks.")
    args = parser.parse_args()
    
    # Konfigurer logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )
    
    print("🧠 Oslomodell Knowledge Ingester (RPC Gateway)")
    print("="*60)
    
    load_dotenv()
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gateway_url = os.getenv("RPC_GATEWAY_URL")

    if not all([gemini_api_key, gateway_url]):
        logger.error("Nødvendige miljøvariabler mangler: GEMINI_API_KEY, RPC_GATEWAY_URL. Sjekk din .env-fil.")
        sys.exit(1)

    # Initialiser ekte klienter
    embedding_gateway = EmbeddingGateway(api_key=gemini_api_key)
    
    async with RPCGatewayClient(agent_id="knowledge_ingester", gateway_url=gateway_url) as rpc_client:
        ingester = KnowledgeIngester(
            embedding_gateway=embedding_gateway,
            rpc_gateway_client=rpc_client
        )
        await ingester.ingest_csv(filepath=args.csv_file)

    print("="*60)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())