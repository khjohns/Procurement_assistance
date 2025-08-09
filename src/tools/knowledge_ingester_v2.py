#!/usr/bin/env python3
"""
knowledge_ingester.py v2 - Generell og fleksibel knowledge base ingester
Erstatter spesifikke load_*_knowledge.py scripts med en konfigurerbar løsning.

Støtter:
- CSV import med auto-detect av delimiter (komma/semikolon)  
- Konfigurerbar kolonne-mapping
- Automatisk chunking av lange dokumenter
- Fleksibel metadata håndtering
- Embedding generering via RPC Gateway
- Support for multiple knowledge bases (oslomodell, miljokrav, etc.)

Usage:
    python src/tools/knowledge_ingester.py --config configs/oslomodell_config.yaml --csv data/oslomodell.csv
    python src/tools/knowledge_ingester.py --config configs/miljokrav_config.yaml --csv data/miljokrav.csv
"""

import os
import sys
import asyncio
import csv
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import structlog
import yaml
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.rpc_gateway_client import RPCGatewayClient
from src.tools.embedding_gateway import EmbeddingGateway

logger = structlog.get_logger()

@dataclass
class IngesterConfig:
    """Configuration for knowledge ingestion."""
    # Knowledge base settings
    knowledge_base: str  # 'oslomodell' or 'miljokrav'
    rpc_method: str     # 'database.store_knowledge_document' or 'database.store_miljokrav_document'
    
    # CSV mapping
    id_column: str
    content_column: str
    metadata_columns: List[str]
    
    # Chunking settings
    enable_chunking: bool = False
    chunk_size: int = 1000
    chunk_overlap: int = 100
    
    # Processing settings
    id_prefix: str = ""
    content_preprocessing: Optional[str] = None  # 'clean', 'markdown_to_text', etc.
    
    # Metadata settings
    static_metadata: Dict[str, Any] = None
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'IngesterConfig':
        """Load configuration from YAML file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls(
            knowledge_base=data['knowledge_base'],
            rpc_method=data['rpc_method'],
            id_column=data['csv_mapping']['id_column'],
            content_column=data['csv_mapping']['content_column'],
            metadata_columns=data['csv_mapping'].get('metadata_columns', []),
            enable_chunking=data.get('chunking', {}).get('enabled', False),
            chunk_size=data.get('chunking', {}).get('size', 1000),
            chunk_overlap=data.get('chunking', {}).get('overlap', 100),
            id_prefix=data.get('processing', {}).get('id_prefix', ''),
            content_preprocessing=data.get('processing', {}).get('content_preprocessing'),
            static_metadata=data.get('metadata', {}).get('static', {})
        )

class CSVReader:
    """Smart CSV reader with auto-detection of delimiter and encoding."""
    
    @staticmethod
    def detect_delimiter(file_path: str, sample_size: int = 5) -> str:
        """Detect CSV delimiter by sampling first few lines."""
        with open(file_path, 'r', encoding='utf-8') as f:
            sample_lines = [f.readline() for _ in range(sample_size)]
        
        sample_text = ''.join(sample_lines)
        
        # Count occurrences of common delimiters
        delimiters = [',', ';', '\t', '|']
        counts = {delim: sample_text.count(delim) for delim in delimiters}
        
        # Return delimiter with highest count
        detected = max(counts, key=counts.get)
        logger.info(f"Detected CSV delimiter: '{detected}' (counts: {counts})")
        return detected
    
    @staticmethod
    def read_csv(file_path: str, delimiter: Optional[str] = None) -> List[Dict[str, str]]:
        """Read CSV file with auto-detection or specified delimiter."""
        if delimiter is None:
            delimiter = CSVReader.detect_delimiter(file_path)
        
        rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Clean headers (strip whitespace)
            clean_fieldnames = [name.strip() for name in reader.fieldnames]
            reader.fieldnames = clean_fieldnames
            
            for row in reader:
                # Clean row values (strip whitespace, handle empty strings)
                clean_row = {}
                for key, value in row.items():
                    if value is not None:
                        clean_value = str(value).strip()
                        clean_row[key] = clean_value if clean_value else None
                    else:
                        clean_row[key] = None
                rows.append(clean_row)
        
        logger.info(f"Read {len(rows)} rows from {file_path}")
        return rows

class ContentProcessor:
    """Handles content preprocessing and chunking."""
    
    @staticmethod
    def preprocess_content(content: str, method: Optional[str] = None) -> str:
        """Apply preprocessing to content."""
        if not method or not content:
            return content
            
        if method == 'clean':
            # Basic cleaning: normalize whitespace, remove extra newlines
            return ' '.join(content.split())
        elif method == 'markdown_to_text':
            # Remove basic markdown formatting
            import re
            content = re.sub(r'[#*_`]', '', content)
            return ' '.join(content.split())
        else:
            logger.warning(f"Unknown preprocessing method: {method}")
            return content
    
    @staticmethod
    def chunk_content(content: str, chunk_size: int, overlap: int) -> List[str]:
        """Split content into overlapping chunks."""
        if len(content) <= chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            
            # Try to break at word boundary
            if end < len(content):
                # Look for last space/punctuation within chunk
                break_point = content.rfind(' ', start, end)
                if break_point > start:
                    end = break_point
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - overlap
            
            # Prevent infinite loop
            if start <= 0:
                start = end
        
        logger.info(f"Split content into {len(chunks)} chunks")
        return chunks

class KnowledgeIngester:
    """Main knowledge ingester class."""
    
    def __init__(self, config: IngesterConfig):
        self.config = config
        self.rpc_client = None
        self.embedding_gateway = None
        
    async def initialize(self):
        """Initialize RPC client and embedding gateway."""
        # Initialize RPC Gateway client
        gateway_url = os.getenv('RPC_GATEWAY_URL', 'http://localhost:8000')
        self.rpc_client = RPCGatewayClient(gateway_url)
        
        # Initialize embedding gateway
        self.embedding_gateway = EmbeddingGateway()
        
        logger.info(f"Initialized ingester for knowledge base: {self.config.knowledge_base}")
    
    def validate_csv_columns(self, sample_row: Dict[str, str]) -> bool:
        """Validate that required columns exist in CSV."""
        required_columns = [self.config.id_column, self.config.content_column]
        required_columns.extend(self.config.metadata_columns)
        
        missing_columns = [col for col in required_columns if col not in sample_row]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            logger.info(f"Available columns: {list(sample_row.keys())}")
            return False
        
        return True
    
    def extract_metadata(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Extract metadata from CSV row."""
        metadata = {}
        
        # Add static metadata
        if self.config.static_metadata:
            metadata.update(self.config.static_metadata)
        
        # Add dynamic metadata from specified columns
        for col in self.config.metadata_columns:
            if col in row and row[col] is not None:
                metadata[col] = row[col]
        
        return metadata
    
    async def process_row(self, row: Dict[str, str], row_index: int) -> List[Dict[str, Any]]:
        """Process a single CSV row into one or more knowledge documents."""
        # Extract basic fields
        base_id = row[self.config.id_column]
        content = row[self.config.content_column]
        
        if not base_id or not content:
            logger.warning(f"Skipping row {row_index}: missing ID or content")
            return []
        
        # Preprocess content
        content = ContentProcessor.preprocess_content(
            content, self.config.content_preprocessing
        )
        
        # Extract metadata
        metadata = self.extract_metadata(row)
        metadata['source_row'] = row_index
        metadata['original_id'] = base_id
        
        # Handle chunking
        if self.config.enable_chunking:
            chunks = ContentProcessor.chunk_content(
                content, self.config.chunk_size, self.config.chunk_overlap
            )
        else:
            chunks = [content]
        
        # Create documents for each chunk
        documents = []
        for chunk_index, chunk_content in enumerate(chunks):
            if len(chunks) > 1:
                doc_id = f"{self.config.id_prefix}{base_id}-{chunk_index:03d}"
                chunk_metadata = metadata.copy()
                chunk_metadata['chunk_index'] = chunk_index
                chunk_metadata['total_chunks'] = len(chunks)
            else:
                doc_id = f"{self.config.id_prefix}{base_id}"
                chunk_metadata = metadata
            
            # Generate embedding
            try:
                embedding = await self.embedding_gateway.get_embedding(chunk_content)
            except Exception as e:
                logger.error(f"Failed to generate embedding for {doc_id}: {e}")
                continue
            
            documents.append({
                'documentId': doc_id,
                'content': chunk_content,
                'embedding': embedding,
                'metadata': chunk_metadata
            })
        
        return documents
    
    async def store_document(self, document: Dict[str, Any]) -> bool:
        """Store a single document via RPC."""
        try:
            result = await self.rpc_client.call(
                self.config.rpc_method,
                document,
                timeout=30
            )
            
            if result.get('status') == 'success':
                logger.debug(f"Stored document: {document['documentId']}")
                return True
            else:
                logger.error(f"Failed to store {document['documentId']}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error storing {document['documentId']}: {e}")
            return False
    
    async def ingest_csv(self, csv_path: str, delimiter: Optional[str] = None) -> Dict[str, int]:
        """Main ingestion method."""
        logger.info(f"Starting ingestion from {csv_path}")
        
        # Read CSV
        rows = CSVReader.read_csv(csv_path, delimiter)
        if not rows:
            raise ValueError("No rows found in CSV file")
        
        # Validate columns
        if not self.validate_csv_columns(rows[0]):
            raise ValueError("CSV validation failed")
        
        stats = {
            'total_rows': len(rows),
            'processed_rows': 0,
            'created_documents': 0,
            'stored_documents': 0,
            'failed_documents': 0
        }
        
        # Process each row
        for row_index, row in enumerate(rows):
            try:
                documents = await self.process_row(row, row_index)
                stats['processed_rows'] += 1
                stats['created_documents'] += len(documents)
                
                # Store each document
                for doc in documents:
                    if await self.store_document(doc):
                        stats['stored_documents'] += 1
                    else:
                        stats['failed_documents'] += 1
                
                # Progress logging
                if (row_index + 1) % 10 == 0:
                    logger.info(f"Processed {row_index + 1}/{len(rows)} rows")
                    
            except Exception as e:
                logger.error(f"Error processing row {row_index}: {e}")
                stats['failed_documents'] += 1
        
        logger.info(f"Ingestion completed: {stats}")
        return stats

async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generell Knowledge Base Ingester")
    parser.add_argument('--config', required=True, help="YAML config file path")
    parser.add_argument('--csv', required=True, help="CSV file to ingest")
    parser.add_argument('--delimiter', help="CSV delimiter (auto-detected if not specified)")
    parser.add_argument('--dry-run', action='store_true', help="Process but don't store")
    
    args = parser.parse_args()
    
    # Load environment
    load_dotenv()
    
    # Load configuration
    try:
        config = IngesterConfig.from_yaml(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1
    
    # Initialize and run ingester
    ingester = KnowledgeIngester(config)
    await ingester.initialize()
    
    if args.dry_run:
        logger.info("DRY RUN MODE - Not storing documents")
        # Could implement dry run logic here
        return 0
    
    try:
        stats = await ingester.ingest_csv(args.csv, args.delimiter)
        
        if stats['failed_documents'] > 0:
            logger.warning(f"Completed with {stats['failed_documents']} failures")
            return 1
        else:
            logger.info("Ingestion completed successfully")
            return 0
            
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)