#!/usr/bin/env python3
"""
document_ingester.py v2 - Generell og fleksibel document ingester
For strukturerte data til vanlige database-tabeller (ikke knowledge bases).

Støtter:
- CSV import med auto-detect av delimiter (komma/semikolon)
- Konfigurerbar kolonne-mapping til database felter
- Datatype konvertering og validering
- Batch processing for performance
- Multiple target tables
- RPC calls til database funksjoner

Usage:
    python src/tools/document_ingester.py --config configs/requirements_config.yaml --csv data/requirements.csv
    python src/tools/document_ingester.py --config configs/suppliers_config.yaml --csv data/suppliers.csv
"""

import os
import sys
import asyncio
import csv
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
import structlog
import yaml
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.rpc_gateway_client import RPCGatewayClient

logger = structlog.get_logger()

@dataclass
class FieldMapping:
    """Mapping configuration for a single field."""
    csv_column: str
    db_field: str
    data_type: str = 'string'  # 'string', 'integer', 'float', 'boolean', 'date', 'json'
    required: bool = False
    default_value: Any = None
    validator: Optional[str] = None  # Name of validation function
    transformer: Optional[str] = None  # Name of transformation function

@dataclass
class TableConfig:
    """Configuration for a target table."""
    table_name: str
    rpc_method: str  # e.g., 'database.insert_requirement', 'database.upsert_supplier'
    batch_size: int = 10
    upsert: bool = False  # If true, update existing records
    key_fields: List[str] = field(default_factory=list)  # Fields for conflict resolution

@dataclass
class IngesterConfig:
    """Configuration for document ingestion."""
    # Target configuration
    target: TableConfig
    
    # Field mappings
    field_mappings: List[FieldMapping]
    
    # Processing settings
    skip_header_rows: int = 0
    max_rows: Optional[int] = None
    continue_on_error: bool = True
    
    # Validation settings
    validate_required_fields: bool = True
    validate_data_types: bool = True
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'IngesterConfig':
        """Load configuration from YAML file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Parse target configuration
        target_data = data['target']
        target = TableConfig(
            table_name=target_data['table_name'],
            rpc_method=target_data['rpc_method'],
            batch_size=target_data.get('batch_size', 10),
            upsert=target_data.get('upsert', False),
            key_fields=target_data.get('key_fields', [])
        )
        
        # Parse field mappings
        field_mappings = []
        for mapping_data in data['field_mappings']:
            mapping = FieldMapping(
                csv_column=mapping_data['csv_column'],
                db_field=mapping_data['db_field'],
                data_type=mapping_data.get('data_type', 'string'),
                required=mapping_data.get('required', False),
                default_value=mapping_data.get('default_value'),
                validator=mapping_data.get('validator'),
                transformer=mapping_data.get('transformer')
            )
            field_mappings.append(mapping)
        
        return cls(
            target=target,
            field_mappings=field_mappings,
            skip_header_rows=data.get('processing', {}).get('skip_header_rows', 0),
            max_rows=data.get('processing', {}).get('max_rows'),
            continue_on_error=data.get('processing', {}).get('continue_on_error', True),
            validate_required_fields=data.get('validation', {}).get('required_fields', True),
            validate_data_types=data.get('validation', {}).get('data_types', True)
        )

class CSVReader:
    """Smart CSV reader with auto-detection capabilities."""
    
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
    def read_csv(file_path: str, delimiter: Optional[str] = None, skip_rows: int = 0, max_rows: Optional[int] = None) -> List[Dict[str, str]]:
        """Read CSV file with auto-detection or specified delimiter."""
        if delimiter is None:
            delimiter = CSVReader.detect_delimiter(file_path)
        
        rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            # Skip header rows if specified
            for _ in range(skip_rows):
                f.readline()
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Clean headers (strip whitespace)
            clean_fieldnames = [name.strip() for name in reader.fieldnames if name]
            reader.fieldnames = clean_fieldnames
            
            for row_num, row in enumerate(reader):
                if max_rows and row_num >= max_rows:
                    break
                
                # Clean row values
                clean_row = {}
                for key, value in row.items():
                    if key and value is not None:
                        clean_value = str(value).strip()
                        clean_row[key] = clean_value if clean_value else None
                    else:
                        clean_row[key] = None
                rows.append(clean_row)
        
        logger.info(f"Read {len(rows)} rows from {file_path}")
        return rows

class DataProcessor:
    """Handles data validation, transformation and type conversion."""
    
    # Built-in validators
    VALIDATORS = {
        'email': lambda x: '@' in str(x) if x else True,
        'url': lambda x: str(x).startswith(('http://', 'https://')) if x else True,
        'not_empty': lambda x: bool(str(x).strip()) if x else False,
        'positive_number': lambda x: float(x) > 0 if x else True,
        'valid_code': lambda x: str(x).isalnum() if x else True
    }
    
    # Built-in transformers
    TRANSFORMERS = {
        'uppercase': lambda x: str(x).upper() if x else x,
        'lowercase': lambda x: str(x).lower() if x else x,
        'trim': lambda x: str(x).strip() if x else x,
        'normalize_space': lambda x: ' '.join(str(x).split()) if x else x,
        'remove_quotes': lambda x: str(x).strip('\'"') if x else x
    }
    
    @classmethod
    def convert_type(cls, value: Any, target_type: str) -> Any:
        """Convert value to specified type."""
        if value is None or value == '':
            return None
        
        try:
            if target_type == 'string':
                return str(value)
            elif target_type == 'integer':
                return int(float(value))  # Handle "123.0" strings
            elif target_type == 'float':
                return float(value)
            elif target_type == 'boolean':
                if isinstance(value, bool):
                    return value
                str_val = str(value).lower()
                return str_val in ('true', '1', 'yes', 'on', 'ja')
            elif target_type == 'date':
                if isinstance(value, str):
                    # Try common date formats
                    for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']:
                        try:
                            return datetime.strptime(value, fmt).date().isoformat()
                        except ValueError:
                            continue
                return str(value)  # Return as string if parsing fails
            elif target_type == 'json':
                if isinstance(value, str):
                    return json.loads(value)
                return value
            else:
                logger.warning(f"Unknown data type: {target_type}")
                return str(value)
        except Exception as e:
            logger.warning(f"Type conversion failed for value '{value}' to {target_type}: {e}")
            return value
    
    @classmethod
    def validate_value(cls, value: Any, validator_name: str) -> bool:
        """Validate value using built-in or custom validator."""
        if validator_name in cls.VALIDATORS:
            return cls.VALIDATORS[validator_name](value)
        else:
            logger.warning(f"Unknown validator: {validator_name}")
            return True
    
    @classmethod
    def transform_value(cls, value: Any, transformer_name: str) -> Any:
        """Transform value using built-in or custom transformer."""
        if transformer_name in cls.TRANSFORMERS:
            return cls.TRANSFORMERS[transformer_name](value)
        else:
            logger.warning(f"Unknown transformer: {transformer_name}")
            return value

class DocumentIngester:
    """Main document ingester class."""
    
    def __init__(self, config: IngesterConfig):
        self.config = config
        self.rpc_client = None
        
    async def initialize(self):
        """Initialize RPC client."""
        gateway_url = os.getenv('RPC_GATEWAY_URL', 'http://localhost:8000')
        self.rpc_client = RPCGatewayClient(gateway_url)
        
        logger.info(f"Initialized ingester for table: {self.config.target.table_name}")
    
    def validate_csv_columns(self, sample_row: Dict[str, str]) -> bool:
        """Validate that required CSV columns exist."""
        required_columns = [mapping.csv_column for mapping in self.config.field_mappings]
        missing_columns = [col for col in required_columns if col not in sample_row]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            logger.info(f"Available columns: {list(sample_row.keys())}")
            return False
        
        return True
    
    def process_row(self, row: Dict[str, str], row_index: int) -> Optional[Dict[str, Any]]:
        """Process a single CSV row into a database record."""
        record = {}
        errors = []
        
        for mapping in self.config.field_mappings:
            csv_value = row.get(mapping.csv_column)
            
            # Handle missing values
            if csv_value is None or csv_value == '':
                if mapping.required and self.config.validate_required_fields:
                    errors.append(f"Required field '{mapping.csv_column}' is missing")
                    continue
                elif mapping.default_value is not None:
                    csv_value = mapping.default_value
                else:
                    record[mapping.db_field] = None
                    continue
            
            # Apply transformer
            if mapping.transformer:
                csv_value = DataProcessor.transform_value(csv_value, mapping.transformer)
            
            # Convert type
            if self.config.validate_data_types:
                try:
                    converted_value = DataProcessor.convert_type(csv_value, mapping.data_type)
                except Exception as e:
                    errors.append(f"Type conversion failed for '{mapping.csv_column}': {e}")
                    continue
            else:
                converted_value = csv_value
            
            # Validate
            if mapping.validator and not DataProcessor.validate_value(converted_value, mapping.validator):
                errors.append(f"Validation failed for '{mapping.csv_column}' with value '{converted_value}'")
                continue
            
            record[mapping.db_field] = converted_value
        
        # Handle errors
        if errors:
            if self.config.continue_on_error:
                logger.warning(f"Row {row_index} has errors but continuing: {errors}")
                return None
            else:
                raise ValueError(f"Row {row_index} validation failed: {errors}")
        
        return record
    
    async def store_batch(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        """Store a batch of records via RPC."""
        stats = {'success': 0, 'failed': 0}
        
        for record in records:
            try:
                result = await self.rpc_client.call(
                    self.config.target.rpc_method,
                    record,
                    timeout=30
                )
                
                if result.get('status') == 'success':
                    stats['success'] += 1
                    logger.debug(f"Stored record: {record.get('id', 'unknown')}")
                else:
                    stats['failed'] += 1
                    logger.error(f"Failed to store record: {result}")
                    
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"Error storing record: {e}")
        
        return stats
    
    async def ingest_csv(self, csv_path: str, delimiter: Optional[str] = None) -> Dict[str, int]:
        """Main ingestion method."""
        logger.info(f"Starting ingestion from {csv_path}")
        
        # Read CSV
        rows = CSVReader.read_csv(
            csv_path, 
            delimiter, 
            self.config.skip_header_rows, 
            self.config.max_rows
        )
        
        if not rows:
            raise ValueError("No rows found in CSV file")
        
        # Validate columns
        if not self.validate_csv_columns(rows[0]):
            raise ValueError("CSV validation failed")
        
        stats = {
            'total_rows': len(rows),
            'processed_rows': 0,
            'valid_records': 0,
            'stored_records': 0,
            'failed_records': 0
        }
        
        # Process rows in batches
        batch = []
        batch_size = self.config.target.batch_size
        
        for row_index, row in enumerate(rows):
            try:
                record = self.process_row(row, row_index)
                stats['processed_rows'] += 1
                
                if record:
                    batch.append(record)
                    stats['valid_records'] += 1
                
                # Process batch when full or at end
                if len(batch) >= batch_size or row_index == len(rows) - 1:
                    if batch:
                        batch_stats = await self.store_batch(batch)
                        stats['stored_records'] += batch_stats['success']
                        stats['failed_records'] += batch_stats['failed']
                        batch = []
                
                # Progress logging
                if (row_index + 1) % 100 == 0:
                    logger.info(f"Processed {row_index + 1}/{len(rows)} rows")
                    
            except Exception as e:
                if not self.config.continue_on_error:
                    raise
                logger.error(f"Error processing row {row_index}: {e}")
                stats['failed_records'] += 1
        
        logger.info(f"Ingestion completed: {stats}")
        return stats

async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generell Document Ingester")
    parser.add_argument('--config', required=True, help="YAML config file path")
    parser.add_argument('--csv', required=True, help="CSV file to ingest")
    parser.add_argument('--delimiter', help="CSV delimiter (auto-detected if not specified)")
    parser.add_argument('--dry-run', action='store_true', help="Process but don't store")
    parser.add_argument('--verbose', action='store_true', help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
        )
    
    # Load environment
    load_dotenv()
    
    # Load configuration
    try:
        config = IngesterConfig.from_yaml(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1
    
    # Initialize and run ingester
    ingester = DocumentIngester(config)
    await ingester.initialize()
    
    if args.dry_run:
        logger.info("DRY RUN MODE - Not storing records")
        # Could implement dry run logic here
        return 0
    
    try:
        stats = await ingester.ingest_csv(args.csv, args.delimiter)
        
        if stats['failed_records'] > 0:
            logger.warning(f"Completed with {stats['failed_records']} failures")
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