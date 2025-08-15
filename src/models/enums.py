# src/models/enums.py
"""
Centralized enum definitions for the AI Agent SDK.
All enum values are in Norwegian (lowercase) for consistency.
All enum names and docstrings are in English.
"""
from enum import Enum

# ==============================================================================
# SYSTEM-WIDE ENUMS
# ==============================================================================

class Language(str, Enum):
    """System language configuration."""
    NORWEGIAN = "no"
    ENGLISH = "en"

class SystemStatus(str, Enum):
    """Universal status enum."""
    ACTIVE = "aktiv"
    PENDING = "venter"
    PROCESSED = "behandlet"
    ERROR = "feil"
    ARCHIVED = "arkivert"

class RiskLevel(str, Enum):
    """Risk levels used across all agents."""
    NONE = "ingen"
    LOW = "lav"
    MEDIUM = "moderat"
    HIGH = "høy"
    CRITICAL = "kritisk"

# ==============================================================================
# PROCUREMENT ENUMS
# ==============================================================================

class ProcurementCategory(str, Enum):
    """Main procurement categories."""
    GOODS = "vare"
    SERVICE = "tjeneste"
    CONSTRUCTION = "bygg"
    CIVIL_ENGINEERING = "anlegg"
    CLEANING = "renhold"

class ProcurementSubCategory(str, Enum):
    """Specialized procurement categories."""
    ICT = "ikt"
    CONSULTANT = "konsulent"
    TRANSPORT = "transport"
    CATERING = "kantine"
    SECURITY = "sikkerhet"
    MAINTENANCE = "vedlikehold"

class ContractType(str, Enum):
    """Contract types."""
    STANDARD = "standard"
    RESERVED = "reservert"
    FRAMEWORK = "rammeavtale"
    JOINT_PURCHASE = "samkjøpsavtale"
    DYNAMIC = "dynamisk"

class ProcurementPhase(str, Enum):
    """Procurement process phases."""
    PLANNING = "planlegging"
    TENDER = "utlysning"
    EVALUATION = "evaluering"
    CONTRACT_AWARD = "kontraktstildeling"
    CONTRACT_FOLLOW_UP = "kontraktsoppfølging"

# ==============================================================================
# ACTOR ENUMS
# ==============================================================================

class Actor(str, Enum):
    """Roles and organizations in procurement."""
    UKE = "utviklings- og kompetanseetaten"
    OBF = "oslobygg kf"
    SUPPLIER = "leverandør"
    CLIENT = "oppdragsgiver"
    CITY_COUNCIL = "byrådet"
    AGENCY = "virksomhet"
    BYM = "bymiljøetaten"
    SUBCONTRACTOR = "underleverandør"

# ==============================================================================
# REQUIREMENT ENUMS
# ==============================================================================

class RequirementType(str, Enum):
    """Types of requirements in procurement."""
    QUALIFICATION = "kvalifikasjonskrav"
    CONTRACT = "kontraktskrav"
    MINIMUM = "minimumskrav"
    AWARD_CRITERION = "tildelingskriterium"
    INCENTIVE = "insentiv"
    DOCUMENTATION = "dokumentasjonskrav"

class RequirementSource(str, Enum):
    """Source of requirements."""
    OSLOMODELL = "oslomodellen"
    ENVIRONMENT = "miljøkrav"
    PROCUREMENT_REGULATION = "anskaffelsesforskrift"
    INTERNAL = "internt"
    OTHER = "annet"

class RequirementCategory(str, Enum):
    """Requirement categories."""
    INTEGRITY = "seriøsitet"
    DUE_DILIGENCE = "aktsomhet"
    APPRENTICES = "lærlinger"
    ENVIRONMENT = "miljø"
    CLIMATE = "klima"
    TRANSPORT = "transport"
    MACHINES = "maskiner"
    DOCUMENTATION = "dokumentasjon"
    OTHER = "annet"

class RuleStatus(str, Enum):
    """Lifecycle status of rules."""
    ACTIVE = "aktiv"
    PROPOSED = "foreslått"
    EXPIRED = "utløpt"
    SUPERSEDED = "erstattet"
    PHASING_OUT = "utfases"

class ConditionOperator(str, Enum):
    """Operators for rule conditions."""
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "="
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    CONTAINS = "contains"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"

# ==============================================================================
# RISK ENUMS
# ==============================================================================

class RiskType(str, Enum):
    """Types of risks in procurement."""
    LABOR_CRIME = "arbeidslivskriminalitet"
    SOCIAL_DUMPING = "sosial_dumping"
    ENVIRONMENT = "miljø"
    CLIMATE = "klima"
    CORRUPTION = "korrupsjon"
    HUMAN_RIGHTS = "menneskerettigheter"
    INTERNATIONAL_LAW = "internasjonal_humanitærrett"
    OCCUPATION = "ulovlig_okkupasjon"
    DATA_SECURITY = "datasikkerhet"
    NONE = "ingen"

# ==============================================================================
# OSLOMODELL-SPECIFIC ENUMS
# ==============================================================================

class DueDiligenceRequirement(str, Enum):
    """Due diligence requirement sets (Oslomodell point 7)."""
    SET_A = "kravsett_a"  # Standard requirements
    SET_B = "kravsett_b"  # Simplified requirements
    GENERAL = "generell_vurdering"  # General assessment only
    NONE = "ikke_påkrevd"

class ReservedContractArea(str, Enum):
    """Areas for reserved contracts (Oslomodell point 8)."""
    PRINTING = "trykking_kopiering"
    PACKAGING = "pakking_emballering"
    FRUIT = "fruktordninger"
    CATERING = "catering"
    TIRE_HOTEL = "dekkhotell"
    TRANSPORT = "distribusjon_transport"
    ASSEMBLY = "monteringsoppdrag"
    SIGN_PRODUCTION = "skiltproduksjon"
    TEXTILE = "søm_reparasjoner_tekstiltrykk"

class ContractualObligation(str, Enum):
    """Contract follow-up obligations."""
    SANCTIONS = "sanksjoner_rutiner"
    FOLLOW_UP = "oppfølging_seriøsitetskrav"
    USE_SYSTEM = "bruk_system"
    WORK_CARD = "bruk_hmskort"
    MANPOWER_LISTS = "mannskapslister_oppfølging"
    INCIDENT_HANDLING = "hendelseshåndtering"
    SITE_CONTROL = "stedlig_kontroll"
    RISK_BASED_CONTROL = "risikobasert_kontroll"

# ==============================================================================
# ENVIRONMENTAL ENUMS
# ==============================================================================

class EnvironmentalRequirementType(str, Enum):
    """Types of environmental requirements."""
    EMISSION_FREE = "utslippsfri"
    BIOGAS = "biogass"
    BIODIESEL = "bærekraftig_biodrivstoff"
    STANDARD_ENV = "standard_miljøkrav"
    CIRCULAR = "sirkulær"
    FOSSIL_FREE = "fossilfri"

class TransportType(str, Enum):
    """Transport types in procurement."""
    MASS_TRANSPORT = "massetransport"
    PERSON_TRANSPORT = "persontransport"
    GOODS_TRANSPORT = "varetransport"
    CONSTRUCTION_TRANSPORT = "anleggstransport"
    NONE = "ingen"

# ==============================================================================
# DOCUMENT ENUMS
# ==============================================================================

class DocumentType(str, Enum):
    """Document types in knowledge base."""
    INSTRUCTION = "instruks"
    COUNCIL_DECISION = "byrådssak"
    CONTRACT_TEMPLATE = "kontraktsmal"
    PROTOCOL = "protokoll"
    GUIDE = "veileder"
    REGULATION = "forskrift"
    ACT = "lov"
    STANDARD = "standard"
    REPORT = "rapport"

class ChunkLevel(str, Enum):
    """Hierarchical level of content chunks."""
    DOCUMENT = "dokument"
    SECTION = "seksjon"
    SUBSECTION = "underseksjon"
    RULE = "regel"
    EXAMPLE = "eksempel"
    DEFINITION = "definisjon"
    REQUIREMENT = "krav"
    PARAGRAPH = "avsnitt"

# I enums.py, legg til:
class ChunkType(str, Enum):
    """Type of content chunk."""
    RULE = "regel"           # Chunks med rule_sets og strukturerte betingelser
    CONTEXT = "kontekst"     # Politiske føringer, vurderinger
    GUIDANCE = "veiledning"  # Praktisk veiledning
    EXAMPLE = "eksempel"     # Eksempler på anvendelse
    DEFINITION = "definisjon" # Definisjoner

# ==============================================================================
# ASSESSMENT ENUMS
# ==============================================================================

class TriageColor(str, Enum):
    """Triage classification colors."""
    GREEN = "grønn"
    YELLOW = "gul"
    RED = "rød"

class FollowUpTool(str, Enum):
    """Contract follow-up tools."""
    HMSREG = "hmsreg"
    CONTRACT_SYSTEM = "kontraktsoppfølgingssystem"
    SUPPLIER_PORTAL = "leverandørportal"

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_enum_by_value(enum_class: type[Enum], value: str) -> Enum:
    """
    Get enum member by its value.
    
    Args:
        enum_class: The enum class to search in
        value: The value to search for
        
    Returns:
        The enum member with the given value
        
    Raises:
        ValueError: If value not found
    """
    for member in enum_class:
        if member.value == value:
            return member
    raise ValueError(f"No {enum_class.__name__} with value '{value}'")

def get_all_values(enum_class: type[Enum]) -> list[str]:
    """Get all values from an enum class."""
    return [member.value for member in enum_class]