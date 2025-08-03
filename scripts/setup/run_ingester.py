import asyncio
import os
from dotenv import load_dotenv
import structlog

from tools.simple_supabase_gateway import SupabaseGatewayManager
from tools.embedding_gateway import EmbeddingGateway
from tools.knowledge_ingester import KnowledgeIngester

# Sett opp logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

async def main():
    """Hovedfunksjon for å kjøre ingest-prosessen."""
    load_dotenv()
    logger.info("Starting knowledge base ingestion process...")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in .env file")
        return

    try:
        async with SupabaseGatewayManager() as supabase_gateway:
            embedding_gateway = EmbeddingGateway(api_key=api_key)
            
            ingester = KnowledgeIngester(
                supabase_gateway=supabase_gateway,
                embedding_gateway=embedding_gateway
            )
            
            csv_path = "kunnskapsbase.csv"
            logger.info(f"Ingesting from {csv_path}")
            await ingester.ingest_from_csv(csv_path)
            logger.info("Ingestion process completed successfully.")

    except Exception as e:
        logger.error("An error occurred during the ingestion process", error=str(e), exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
