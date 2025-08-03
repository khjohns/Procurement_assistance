import pandas as pd
from typing import List, Dict, Optional
import asyncio
from pathlib import Path
from src.tools.embedding_gateway import EmbeddingGateway
from src.tools.simple_supabase_gateway import SupabaseGateway
import structlog

logger = structlog.get_logger()

class KnowledgeIngester:
    """Verktøy for å bygge hybrid RAG kunnskapsbase"""
    
    def __init__(self, supabase_gateway: SupabaseGateway, embedding_gateway: EmbeddingGateway):
        self.db = supabase_gateway
        self.embedder = embedding_gateway
    
    async def ingest_from_csv(self, csv_path: str):
        """
        Ingest fra ferdig forberedt CSV med kolonner.
        Prosesserer en og en for å feilsøke batch-problemer.
        """
        df = pd.read_csv(csv_path)
        
        logger.info("Creating document record for CSV ingest.")
        dokument_id = await self.db.create_document_record(
            navn=Path(csv_path).stem,
            type="instruks"
        )
        logger.info(f"Document record created with ID: {dokument_id}")
        
        # Prosesser og lagre hver chunk individuelt
        for idx, row in df.iterrows():
            logger.info(f"Processing chunk {idx+1}/{len(df)}: {row['innhold'][:60]}...")
            metadata = {
                "tema": row.get('tema', ''),
                "paragraf": row.get('paragraf', ''),
                "nøkkelord": row.get('nøkkelord', '').split(',')
            }
            
            # Generer embedding for én enkelt tekst
            embedding = await self.embedder.create_embedding(
                text=row['innhold'],
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=1536 # Eksplisitt satt
            )
            
            logger.info(f"Generated embedding with dimension: {len(embedding)}")

            # Lagre chunk med generert embedding
            await self.db.store_chunk(
                dokument_id=dokument_id,
                innhold=row['innhold'],
                metadata=metadata,
                embedding=embedding,
                chunk_nummer=idx
            )
            
            logger.info(f"✅ Successfully stored chunk {idx+1}")