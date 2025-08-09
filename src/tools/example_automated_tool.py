# src/tools/threshold_calculator.py
"""
Example of a Level 4 (N4) automated tool using the SDK.
This is a deterministic tool that doesn't use LLM.
"""
from typing import Dict, Any
import structlog
from datetime import datetime

from src.agent_library.core import BaseAutomatedTool
from src.agent_library.registry import register_tool
from src.agent_library.decorators import build_metadata
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# Define schemas for validation
class ThresholdInput(BaseModel):
    """Input schema for threshold calculation."""
    value: int = Field(..., description="Anskaffelsesverdi i NOK")
    category: str = Field(..., description="Kategori (varer/tjenester/bygg)")
    
class ThresholdOutput(BaseModel):
    """Output schema for threshold calculation."""
    value: int
    national_threshold_exceeded: bool
    eu_threshold_exceeded: bool
    procurement_type: str  # "Direkte", "Begrenset", "Åpen"
    applicable_regulations: list[str]
    deadlines: Dict[str, int]  # Frister i dager

# Build metadata
THRESHOLD_METADATA = build_metadata(
    description="Beregner terskelverdier og identifiserer gjeldende regelverk",
    input_schema_class=ThresholdInput,
    output_schema_class=ThresholdOutput,
    additional_info={
        "version": "1.0",
        "last_updated": "2025-08-05",
        "deterministic": True
    }
)

@register_tool(
    name="tool.calculate_thresholds",
    service_type="automated_tool",
    metadata=THRESHOLD_METADATA,
    dependencies=[]  # No dependencies needed for deterministic calculations
)
class ThresholdCalculator(BaseAutomatedTool):
    """
    N4 Automated Tool: Calculates procurement thresholds and regulations.
    
    This is a deterministic tool that doesn't require any external services.
    All thresholds are hardcoded based on Norwegian regulations.
    """
    
    def __init__(self):
        super().__init__()
        
        # Nasjonale terskelverdier (2025)
        self.national_thresholds = {
            "varer": 1_300_000,
            "tjenester": 1_300_000,
            "bygg": 13_000_000,
            "særlige_tjenester": 7_500_000,
            "plan_prosjektering": 1_300_000
        }
        
        # EØS-terskelverdier (2025)
        self.eu_thresholds = {
            "varer": 1_775_000,
            "tjenester": 1_775_000,
            "bygg": 68_900_000,
            "særlige_tjenester": 7_500_000,
            "forsyning_varer": 5_325_000,
            "forsyning_tjenester": 5_325_000
        }
        
        # Minimumsfrister (dager)
        self.deadlines = {
            "direkte": 0,
            "begrenset_nasjonal": 10,
            "åpen_nasjonal": 20,
            "begrenset_eøs": 30,
            "åpen_eøs": 35,
            "åpen_eøs_elektronisk": 30
        }
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute threshold calculation.
        
        This is deterministic - no AI, just business rules.
        """
        value = params.get("value", 0)
        category = params.get("category", "tjenester").lower()
        
        logger.info("Calculating thresholds", 
                   value=value, 
                   category=category)
        
        # Get relevant thresholds
        national_limit = self.national_thresholds.get(category, 1_300_000)
        eu_limit = self.eu_thresholds.get(category, 1_775_000)
        
        # Determine procurement type
        if value < 100_000:
            procurement_type = "Direkte anskaffelse"
            applicable_deadlines = {"minimum_frist": self.deadlines["direkte"]}
            regulations = ["Ingen formkrav under 100.000 NOK"]
            
        elif value < national_limit:
            procurement_type = "Begrenset anbudskonkurranse"
            applicable_deadlines = {
                "tilbudsfrist": self.deadlines["begrenset_nasjonal"],
                "vedståelsesfrist": 30
            }
            regulations = [
                "Anskaffelsesforskriften del I",
                "Krav om protokoll",
                "Minimum 3 leverandører skal forespørres"
            ]
            
        elif value < eu_limit:
            procurement_type = "Åpen anbudskonkurranse (nasjonal)"
            applicable_deadlines = {
                "tilbudsfrist": self.deadlines["åpen_nasjonal"],
                "vedståelsesfrist": 60,
                "klagefrist": 10
            }
            regulations = [
                "Anskaffelsesforskriften del II",
                "Kunngjøring på Doffin",
                "Kvalifikasjonskrav tillatt",
                "Tildelingskriterier må oppgis"
            ]
            
        else:
            procurement_type = "Åpen anbudskonkurranse (EØS)"
            applicable_deadlines = {
                "tilbudsfrist": self.deadlines["åpen_eøs"],
                "tilbudsfrist_elektronisk": self.deadlines["åpen_eøs_elektronisk"],
                "vedståelsesfrist": 90,
                "karensperiode": 10,
                "klagefrist": 15
            }
            regulations = [
                "Anskaffelsesforskriften del III",
                "Kunngjøring på Doffin og TED",
                "ESPD-skjema påkrevd",
                "Strenge dokumentasjonskrav",
                "Karensperiode før kontraktsinngåelse"
            ]
        
        # Add Oslo-specific requirements
        if value >= 500_000:
            regulations.append("Oslomodellen: Seriøsitetskrav")
        if value >= 1_750_000:
            regulations.append("Oslomodellen: Krav om lærlinger")
        
        result = {
            "value": value,
            "national_threshold_exceeded": value >= national_limit,
            "eu_threshold_exceeded": value >= eu_limit,
            "procurement_type": procurement_type,
            "applicable_regulations": regulations,
            "deadlines": applicable_deadlines
        }
        
        logger.info("Threshold calculation completed",
                   procurement_type=procurement_type,
                   regulation_count=len(regulations))
        
        return result
    
    def validate_input(self, params: Dict[str, Any]) -> bool:
        """
        Custom validation for business rules.
        """
        value = params.get("value", 0)
        category = params.get("category", "")
        
        # Value must be non-negative
        if value < 0:
            logger.error("Negative value not allowed", value=value)
            return False
        
        # Category must be valid
        valid_categories = list(self.national_thresholds.keys())
        if category.lower() not in valid_categories:
            logger.warning("Unknown category, using default", 
                         category=category,
                         valid_categories=valid_categories)
            # Don't fail, just warn
        
        return True


# Example: Protocol Template Generator (Another N4 tool)
@register_tool(
    name="tool.generate_protocol_template",
    service_type="automated_tool",
    metadata={
        "description": "Genererer mal for anskaffelsesprotokoll basert på type og verdi",
        "deterministic": True
    },
    dependencies=[]
)
class ProtocolTemplateGenerator(BaseAutomatedTool):
    """
    N4 Tool: Generates protocol templates based on rules.
    No AI needed - just template selection based on criteria.
    """
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate appropriate protocol template."""
        value = params.get("value", 0)
        procurement_type = params.get("procurement_type", "")
        
        if value < 100_000:
            template = self._get_simple_template()
        elif value < 1_300_000:
            template = self._get_national_template()
        else:
            template = self._get_eu_template()
        
        return {
            "template": template,
            "required_sections": self._get_required_sections(value),
            "optional_sections": self._get_optional_sections(value)
        }
    
    def _get_simple_template(self) -> str:
        return """
# Anskaffelsesprotokoll - Forenklet

## 1. Generell informasjon
- Anskaffelsens navn: [FYLL INN]
- Estimert verdi: [FYLL INN]
- Dato: {date}

## 2. Begrunnelse for valg av prosedyre
Direkte anskaffelse under terskelverdi (100.000 NOK)

## 3. Leverandør
- Valgt leverandør: [FYLL INN]
- Organisasjonsnummer: [FYLL INN]
""".format(date=datetime.now().strftime("%Y-%m-%d"))
    
    def _get_national_template(self) -> str:
        # More comprehensive template
        return "... full nasjonal mal ..."
    
    def _get_eu_template(self) -> str:
        # EU-compliant template
        return "... full EØS mal ..."
    
    def _get_required_sections(self, value: int) -> list:
        if value < 100_000:
            return ["Generell info", "Leverandør"]
        elif value < 1_300_000:
            return ["Generell info", "Konkurranse", "Evaluering", "Leverandør"]
        else:
            return ["Generell info", "Kunngjøring", "Kvalifikasjon", 
                   "Evaluering", "Leverandør", "Klagebehandling"]
    
    def _get_optional_sections(self, value: int) -> list:
        return ["Miljøkrav", "Sosiale krav", "Innovasjon"]


# Usage example showing how easy it is to use these tools:
if __name__ == "__main__":
    # Tools are automatically available after import
    from src.agent_library.registry import create_agent_from_registry
    
    # No dependencies needed for automated tools
    container = {}
    
    # Create threshold calculator
    calculator = create_agent_from_registry("tool.calculate_thresholds", container)
    
    # Execute calculation
    result = calculator.execute({
        "value": 2_000_000,
        "category": "tjenester"
    })
    
    print("Threshold calculation:")
    print(f"  Type: {result['procurement_type']}")
    print(f"  Regulations: {result['applicable_regulations']}")
    print(f"  Deadlines: {result['deadlines']}")