import structlog
import os
import google.generativeai as genai
from typing import List

logger = structlog.get_logger()

class EmbeddingGateway:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.embedding_model_name = "gemini-embedding-001"
        logger.info(f"EmbeddingGateway initialized with model: {self.embedding_model_name}")

    async def create_embedding(
        self, 
        text: str, 
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int = 1536
    ) -> List[float]:
        """Genererer en embedding for en gitt tekst med spesifikk task_type."""
        logger.info(
            "Creating embedding", 
            text_length=len(text), 
            task_type=task_type,
            output_dimensionality=output_dimensionality
        )
        try:
            result = await genai.embed_content_async(
                model=self.embedding_model_name,
                content=text,
                task_type=task_type,
                output_dimensionality=output_dimensionality
            )
            return result['embedding']
        except Exception as e:
            logger.error("Error creating embedding", error=str(e), exc_info=True)
            raise

    async def create_batch_embeddings(
        self, 
        texts: List[str], 
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int = 1536
    ) -> List[List[float]]:
        """Genererer embeddings for en liste med tekster ved å bruke riktig batch-metode."""
        logger.info(
            "Creating batch embeddings", 
            num_texts=len(texts), 
            task_type=task_type,
            output_dimensionality=output_dimensionality
        )
        try:
            # Bruk riktig batch-funksjon: embed_content
            response = await genai.embed_content_async(
                model=self.embedding_model_name,
                content=texts,
                task_type=task_type,
                output_dimensionality=output_dimensionality
            )
            # Batch-responsen er en liste av embeddings
            return response['embedding']
        except Exception as e:
            logger.error("Error creating batch embeddings", error=str(e), exc_info=True)
            raise
