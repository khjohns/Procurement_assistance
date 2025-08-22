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
    ANY = "enhver"
    NONE = "ingen"
    LOW = "lav"
    MEDIUM = "moderat"
    HIGH = "høy"

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
    ENERGY = "energi"

    # Verdier fra ReservedContractArea for å matche reglene
    PRINTING = "trykking_kopiering"
    PACKAGING = "pakking_emballering"
    FRUIT = "fruktordninger"
    TIRE_HOTEL = "dekkhotell"
    DISTRIBUTION_TRANSPORT = "distribusjon_transport"
    ASSEMBLY = "monteringsoppdrag"
    SIGN_PRODUCTION = "skiltproduksjon"
    TEXTILE = "søm_reparasjoner_tekstiltrykk"
    CLEANING = "renhold" # Kan overlappe med ProcurementCategory
    LAUNDRY = "vaskeri"

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
    TECHNICAL = "teknisk_krav"
    PERFORMANCE = "ytelseskrav"
    FUNCTIONAL = "funksjonell_krav"
    PROCESS = "prosesskrav"

class RequirementModality(str, Enum):
    """Expresses the legal force of a requirement."""
    MANDATORY = "obligatorisk"      # Represents "skal"
    OPTIONAL = "valgfri"            # Represents "kan"
    PROHIBITED = "forbudt"          # Represents "skal ikke"

class RequirementSource(str, Enum):
    """Source of requirements."""
    OSLOMODELL = "oslomodellen"
    ENVIRONMENT = "miljøkrav"
    PROCUREMENT_REGULATION = "anskaffelsesforskrift"
    INTERNAL = "internt"
    EU_DIRECTIVE = "eu_direktiv"
    NATIONAL_LAW = "nasjonal_lov"
    OTHER = "annet"

class RequirementCategory(str, Enum):
    """Requirement categories."""
    INTEGRITY = "seriøsitet"
    DUE_DILIGENCE = "aktsomhetsvurderinger"
    APPRENTICES = "lærlinger"
    SUBCONTRACTOR_CHAIN = "leverandørkjede"
    ENVIRONMENT = "miljø"
    CLIMATE = "klima"
    TRANSPORT = "transport"
    MACHINES = "maskiner"
    DOCUMENTATION = "dokumentasjon"
    SOCIAL = "sosiale_krav"
    ETHICAL = "etiske_krav"
    INNOVATION = "innovasjon"
    OTHER = "annet"

class RuleStatus(str, Enum):
    """Lifecycle status of rules."""
    ACTIVE = "aktiv"
    PROPOSED = "foreslått"
    EXPIRED = "utløpt"
    SUPERSEDED = "erstattet"
    PHASING_OUT = "utfases"
    DRAFT = "utkast"
    APPROVED = "godkjent"
    SUSPENDED = "suspendert"

class ConditionOperator(str, Enum):
    """Operators for rule conditions."""
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "="
    NEQ = "!="
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"

class RuleField(str, Enum):
    """Fields that can be used in rule conditions."""
    PROCUREMENT_CATEGORY = "anskaffelsestype"
    PROCUREMENT_VALUE = "kontraktsverdi"
    RISK_LEVEL = "risiko"  # General risk level
    RISK_TYPE = "risikotype"  # Specific risk type
    DURATION_YEARS = "kontraktsvarighet_år"
    DURATION_MONTHS = "varighet_måneder"
    SUPPLIER_COUNT = "antall_leverandører"
    INTERNATIONAL = "internasjonal"
    CONSTRUCTION_SITE = "byggeplass"
    TRANSPORT_TYPE = "transporttype"
    ENVIRONMENTAL_ZONE = "miljøsone"
    CONTRACT_TYPE = "kontraktstype"
    RESERVED_AREA = "reservert_område"

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
    QUALITY = "kvalitet"
    DELIVERY = "leveranse"
    FINANCIAL = "økonomi"
    REPUTATION = "omdømme"
    COMPLIANCE = "etterlevelse"
    NONE = "ingen"

# ==============================================================================
# OSLOMODELL-SPECIFIC ENUMS
# ==============================================================================

class DueDiligenceRequirement(str, Enum):
    """Due diligence requirement sets (Oslomodell point 7)."""
    SET_A = "kravsett_a"  # Standard requirements
    SET_B = "kravsett_b"  # Simplified requirements
    GENERAL = "generell_vurdering"  # General assessment only
    ENHANCED = "forsterket_vurdering"  # Enhanced due diligence
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
    CLEANING = "renhold"
    LAUNDRY = "vaskeri"

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
    DOCUMENTATION_CONTROL = "dokumentasjonskontroll"
    AUDIT = "revisjon"

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
    LOW_EMISSION = "lavutslipp"
    EURO_STANDARD = "euro_standard"
    ENERGY_EFFICIENT = "energieffektiv"

class TransportType(str, Enum):
    """Transport types in procurement."""
    MASS_TRANSPORT = "massetransport"
    PERSON_TRANSPORT = "persontransport"
    GOODS_TRANSPORT = "varetransport"
    CONSTRUCTION_TRANSPORT = "anleggstransport"
    WASTE_TRANSPORT = "avfallstransport"
    HEAVY_TRANSPORT = "tungtransport"
    LIGHT_TRANSPORT = "lett_transport"
    NONE = "ingen"

class EmissionStandard(str, Enum):
    """Vehicle emission standards."""
    EURO_6 = "euro_6"
    EURO_5 = "euro_5"
    EURO_4 = "euro_4"
    ELECTRIC = "elektrisk"
    HYDROGEN = "hydrogen"
    HYBRID = "hybrid"
    BIOGAS = "biogass"

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
    POLICY = "politikk"
    PROCEDURE = "prosedyre"
    CHECKLIST = "sjekkliste"

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
    LIST_ITEM = "listepunkt"
    TABLE = "tabell"
    FIGURE = "figur"

class ChunkType(str, Enum):
    """Type of content chunk."""
    RULE = "regel"  # Chunks with rule_sets and structured conditions
    CONTEXT = "kontekst"  # Political context, assessments
    GUIDANCE = "veiledning"  # Practical guidance
    EXAMPLE = "eksempel"  # Application examples
    DEFINITION = "definisjon"  # Definitions
    REQUIREMENT = "krav"  # Specific requirements
    BACKGROUND = "bakgrunn"  # Background information
    REFERENCE = "referanse"  # References to other documents
    WARNING = "advarsel"  # Important warnings
    NOTE = "merknad"  # Additional notes

# ==============================================================================
# ASSESSMENT ENUMS
# ==============================================================================

class TriageColor(str, Enum):
    """Triage classification colors."""
    GREEN = "grønn"
    YELLOW = "gul"
    RED = "rød"

class AssessmentConfidence(str, Enum):
    """Confidence levels for assessments."""
    VERY_LOW = "svært_lav"
    LOW = "lav"
    MEDIUM = "middels"
    HIGH = "høy"
    VERY_HIGH = "svært_høy"

class ReviewStatus(str, Enum):
    """Review status for assessments."""
    NOT_REQUIRED = "ikke_påkrevd"
    PENDING = "venter"
    IN_PROGRESS = "pågår"
    COMPLETED = "fullført"
    REJECTED = "avvist"

# ==============================================================================
# FOLLOW-UP ENUMS
# ==============================================================================

class FollowUpTool(str, Enum):
    """Contract follow-up tools."""
    HMSREG = "hmsreg"
    CONTRACT_SYSTEM = "kontraktsoppfølgingssystem"
    SUPPLIER_PORTAL = "leverandørportal"
    AUDIT_TOOL = "revisjonsverktøy"
    REPORTING_SYSTEM = "rapporteringssystem"

class FollowUpFrequency(str, Enum):
    """Frequency of follow-up activities."""
    CONTINUOUS = "kontinuerlig"
    DAILY = "daglig"
    WEEKLY = "ukentlig"
    MONTHLY = "månedlig"
    QUARTERLY = "kvartalsvis"
    SEMI_ANNUAL = "halvårlig"
    ANNUAL = "årlig"
    AS_NEEDED = "ved_behov"

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

def is_valid_enum_value(enum_class: type[Enum], value: str) -> bool:
    """Check if a value is valid for an enum class."""
    try:
        get_enum_by_value(enum_class, value)
        return True
    except ValueError:
        return False