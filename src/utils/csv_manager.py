# src/utils/csv_manager.py
import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
from threading import Lock
import shutil

class CSVManager:
    """
    En enkel, thread-safe manager for å skrive data til CSV-filer.
    Fokuserer på å legge til rader og initialisere filer.
    """
    
    def __init__(self, data_dir: str = "data/csv"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[str, Lock] = {}
        self._lock_creation_lock = Lock()

        self.csv_configs = {
            'avtaleoversikt': {
                'filename': 'avtaleoversikt.csv',
                'headers': [
                    'procurement_id', 'navn', 'kategori', 'underkategori',
                    'verdi', 'varighet_mnd', 'saksbehandler', 'virksomhet',
                    'saksnummer', 'prosjektnummer', 'opprettet_dato',
                    'sist_oppdatert', 'status', 'assessment_id',
                    'confidence_score', 'anbefalte_krav', 'antall_risikoer',
                    'rapport_generert', 'assessment_summary_prose', 'warnings', 'recommendations'
                ]
            },
            'risk_assessments': {
                'filename': 'risk_assessments.csv',
                'headers': [
                    'assessment_id', 'procurement_id', 'risk_type',
                    'risk_level', 'agent_name', 'confidence',
                    'justification', 'timestamp'
                ]
            },
            'triggered_rules': {
                'filename': 'triggered_rules.csv',
                'headers': [
                    'rule_trigger_id', 'assessment_id', 'procurement_id', 'rule_id',
                    'rule_description', 'priority', 'conditions_met', 
                    'activated_requirements', 'timestamp'
                ]
            },
            'llm_costs': {
                'filename': 'llm_costs.csv',
                'headers': [
                    'cost_id', 'procurement_id', 'assessment_id', 'agent_name',
                    'model', 'purpose', 'input_tokens', 'output_tokens',
                    'total_tokens', 'estimated_cost_usd', 'timestamp'
                ]
            },
            'llm_thoughts': {
                'filename': 'llm_thoughts.csv',
                'headers': [
                    'thought_id', 'assessment_id', 'procurement_id', 'agent_name',
                    'thought_content', 'model', 'timestamp'
                ]
            },
            'supplier_verifications': {
                'filename': 'supplier_verifications.csv',
                'headers': [
                    'verification_id', 'procurement_id', 'assessment_id', 'supplier_name',
                    'org_nr', 'is_foreign', 'obs_status', 'obs_merknad',
                    'konkurs_risiko', 'finansiell_styrke', 'soliditet_prosent',
                    'likviditetsgrad', 'antall_ansatte', 'verification_date', 'verified_by',

                    # --- NYE, DETALJERTE FELT ---
                    'konkurs_begrunnelse',
                    'styrets_stabilitet',
                    'styrets_begrunnelse',
                    'signaturrett',
                    'prokura',
                    'roller',  # Lagres som JSON-streng
                    'finansiell_begrunnelse',
                    'aarsresultat',
                    'detaljerte_finanser' # Lagres som JSON-streng
                ]
            }
        }
        self._initialize_csv_files()

    def _get_lock(self, filename: str) -> Lock:
        """Henter eller oppretter en trådsikker lås for en gitt fil."""
        if filename not in self._locks:
            with self._lock_creation_lock:
                if filename not in self._locks:
                    self._locks[filename] = Lock()
        return self._locks[filename]

    def _initialize_csv_files(self):
        """Sikrer at alle konfigurerte CSV-filer eksisterer og har en header."""
        for config in self.csv_configs.values():
            filepath = self.data_dir / config['filename']
            if not filepath.exists():
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=config['headers'])
                    writer.writeheader()

    def append_row(self, csv_type: str, data: Dict[str, Any]):
        """Legger til en ny rad i en spesifisert CSV-fil på en trådsikker måte."""
        config = self.csv_configs.get(csv_type)
        if not config:
            raise ValueError(f"Ukjent CSV-type: {csv_type}")

        filepath = self.data_dir / config['filename']
        lock = self._get_lock(config['filename'])

        with lock:
            # Bruk 'a' (append) modus for effektivitet
            with open(filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=config['headers'])
                # Skriv kun data, header er allerede der
                writer.writerow(data)

    def update_procurement_record(self, procurement_id: str, update_data: Dict[str, Any]):
        """Oppdaterer en eksisterende rad i avtaleoversikt.csv (ineffektivt, men nødvendig for CSV)."""
        csv_type = 'avtaleoversikt'
        config = self.csv_configs[csv_type]
        filepath = self.data_dir / config['filename']
        lock = self._get_lock(config['filename'])

        temp_filepath = filepath.with_suffix('.tmp')

        with lock:
            with open(filepath, 'r', newline='', encoding='utf-8') as infile, \
                 open(temp_filepath, 'w', newline='', encoding='utf-8') as outfile:
                
                reader = csv.DictReader(infile)
                writer = csv.DictWriter(outfile, fieldnames=config['headers'])
                writer.writeheader()

                found = False
                for row in reader:
                    if row['procurement_id'] == procurement_id:
                        row.update(update_data)
                        found = True
                    writer.writerow(row)
            
            if found:
                shutil.move(str(temp_filepath), str(filepath))
            else:
                os.remove(str(temp_filepath))

    def read_csv(self, csv_type: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Leser data fra en spesifisert CSV-fil, med valgfri filtrering.
        Returnerer en liste med ordbøker.
        """
        config = self.csv_configs.get(csv_type)
        if not config:
            raise ValueError(f"Ukjent CSV-type: {csv_type}")

        filepath = self.data_dir / config['filename']
        if not filepath.exists():
            return []

        lock = self._get_lock(config['filename'])
        with lock:
            try:
                with open(filepath, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
            except Exception as e:
                logger.error("failed_to_read_csv", file=filepath, error=str(e))
                return []

        if filters:
            try:
                # Filtrer data basert på nøkkel-verdi-par
                filtered_data = [
                    row for row in data
                    if all(row.get(key) == value for key, value in filters.items())
                ]
                return filtered_data
            except Exception as e:
                logger.error("failed_to_filter_csv_data", filters=filters, error=str(e))
                return [] # Returner tom liste ved feil

        return data