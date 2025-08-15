# mock_procurement_generator.py

import json
import uuid
from typing import List, Dict, Any
from enum import Enum

# Gjenbruker Enum fra det andre skriptet for konsistens
class ProcurementCategory(str, Enum):
    BYGGE_OG_ANLEGG = "bygge- og anlegg"
    TJENESTE = "tjeneste"
    VARE = "vare"
    RENHOLD = "renhold"
    IKT = "ikt"
    KONSULENT = "konsulent"


def generate_mock_procurements(count: int = 5) -> List[Dict[str, Any]]:
    """
    Genererer en liste med varierte, fiktive anskaffelsesdata for testing.
    """
    
    scenarios = [
        {
            "name": "Oppgradering av Storgata", "category": ProcurementCategory.BYGGE_OG_ANLEGG,
            "value": 25_000_000, "duration_months": 24, "involves_construction": True,
            "description": "Total rehabilitering av gate, inkludert vann og avløp."
        },
        {
            "name": "Nytt saksbehandlingssystem", "category": ProcurementCategory.IKT,
            "value": 1_200_000, "duration_months": 18, "involves_construction": False,
            "description": "Implementering av en skybasert løsning for saksbehandling."
        },
        {
            "name": "Rammeavtale konsulenttjenester (strategi)", "category": ProcurementCategory.KONSULENT,
            "value": 750_000, "duration_months": 12, "involves_construction": False,
            "description": "Innkjøp av strategisk rådgivning for digital transformasjon."
        },
        {
            "name": "Innkjøp av kontorrekvisita", "category": ProcurementCategory.VARE,
            "value": 80_000, "duration_months": 12, "involves_construction": False,
            "description": "Løpende levering av kontorrekvisita til kommunens etater."
        },
        {
            "name": "Vaktmestertjenester for skoler", "category": ProcurementCategory.TJENESTE,
            "value": 950_000, "duration_months": 36, "involves_construction": False,
            "description": "Drift og vedlikehold av 5 skoler i bydel Nord."
        },
         {
            "name": "Kantine- og renholdstjenester", "category": ProcurementCategory.RENHOLD,
            "value": 490_000, "duration_months": 24, "involves_construction": False,
            "description": "Daglig renhold og kantinedrift for et kommunalt kontorbygg."
        }
    ]
    
    # Velg fra listen, og gi unik ID
    generated_mocks = []
    for i in range(count):
        mock = scenarios[i % len(scenarios)].copy() # Roter gjennom scenarioene
        mock["id"] = f"mock-proc-{uuid.uuid4()}"
        
        # Konverter Enum til string for JSON-output
        mock["category"] = mock["category"].value
        generated_mocks.append(mock)
        
    return generated_mocks

def main():
    """
    Hovedfunksjon for å generere og vise frem mock-data.
    """
    print("--- Genererer 5 Mock Anskaffelser ---")
    
    mock_data = generate_mock_procurements(count=5)
    
    # Print som et pent formatert JSON-objekt
    print(json.dumps(mock_data, indent=2, ensure_ascii=False))
    
    print("\n--- Ferdig ---")
    print("Du kan nå kopiere JSON-outputen for å bruke i testene dine.")

if __name__ == "__main__":
    main()