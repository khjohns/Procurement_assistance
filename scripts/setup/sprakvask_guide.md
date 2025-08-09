# 🧹 Komplett Språkvask-guide: Engelske Navnekonvensjoner

## 🎯 Mål
Fjerne alle norske og "svorske" navnekonvensjoner fra kodebasen og erstatte med konsistent engelsk, inkludert ny `dd_risk_assessment` parameter.

## 📋 Identifiserte Problemer

### 1. Python Datamodeller (procurement_models_refactored.py)

**❌ PROBLEMATISKE ENUM-NØKLER:**
```python
class RequirementCategory(str, Enum):
    SERIOSITET = "seriøsitet"      # → INTEGRITY_REQUIREMENTS
    AKTSOMHET = "aktsomhet"        # → DUE_DILIGENCE  
    LARLINGER = "lærlinger"        # → APPRENTICES
    MILJO = "miljø"                # → ENVIRONMENT
    DOKUMENTASJON = "dokumentasjon" # → DOCUMENTATION
```

**✅ RIKTIG ENGELSK VERSJON:**
```python
class RequirementCategory(str, Enum):
    """Kategori for krav."""
    INTEGRITY_REQUIREMENTS = "seriøsitet"     # Integrity/seriousness requirements
    DUE_DILIGENCE = "aktsomhet"               # Due diligence requirements
    APPRENTICES = "lærlinger"                 # Apprenticeship requirements
    ENVIRONMENT = "miljø"                     # Environmental requirements
    CLIMATE = "klima"                         # Climate requirements
    TRANSPORT = "transport"                   # Transport requirements
    DOCUMENTATION = "dokumentasjon"           # Documentation requirements
    OTHER = "annet"                          # Other requirements
```

### 2. Oslomodell Agent - Ny dd_risk_assessment Parameter

**❌ MANGLENDE PARAMETER I PROMPT:**
```python
# Nuværende - bare crime risk
risk_assessment_akrim: "høy"/"moderat"/"lav"
```

**✅ KOMPLETT RISIKOVURDERING:**
```python
# Legg til i prompt template:
crime_risk_assessment: "høy"/"moderat"/"lav"        # var: risk_assessment_akrim
dd_risk_assessment: "høy"/"moderat"/"lav"           # NYE: human rights due diligence
social_dumping_risk: "høy"/"moderat"/"lav"          # var: risk_assessment_social_dumping
```

**OPPDATERING I DATAMODELL:**
```python
class OslomodellAssessmentResult(BaseAssessmentResult):
    assessed_by: str = Field(default="oslomodell_agent")
    
    # Risikovurderinger (alle på norsk for bruker-output)
    crime_risk_assessment: str = Field(..., description="Risiko for kriminalitet")
    dd_risk_assessment: str = Field(..., description="Menneskerettighetsrisiko")  # NYE!
    social_dumping_risk: str = Field(..., description="Sosial dumping-risiko")
```

### 3. Klassenavn og Metoder

**❌ NORSKE/SVORSKE KLASSENAVN:**
```python
class OslomodellDocumentGenerator  # → OsloModelDocumentGenerator
```

**❌ NORSKE METODENAVN:**
```python
def vurder_anskaffelse(self)      # → assess_procurement(self)
def process_anskaffelse(self)     # → process_procurement(self)
```

**✅ ENGELSKE VERSJONER:**
```python
class OsloModelDocumentGenerator:
    def assess_procurement(self):
        pass
    def process_procurement(self):
        pass
```

### 4. Database/RPC Funksjoner

**❌ EKSISTERENDE (i scripts):**
```sql
opprett_anskaffelse          → create_procurement
lagre_triage_resultat        → save_triage_result
```

**✅ ALLEREDE REFAKTORERT** (i hoveddatabasen, men sjekk konsistens)

## 🔧 Implementeringssteg

### Steg 1: Oppdater Procurement Models
```python
# I src/models/procurement_models_refactored.py
class RequirementCategory(str, Enum):
    INTEGRITY_REQUIREMENTS = "seriøsitet"  
    DUE_DILIGENCE = "aktsomhet"
    APPRENTICES = "lærlinger"
    ENVIRONMENT = "miljø"
    CLIMATE = "klima"
    TRANSPORT = "transport"
    DOCUMENTATION = "dokumentasjon"
    OTHER = "annet"

class OslomodellAssessmentResult(BaseAssessmentResult):
    # Legg til ny parameter
    crime_risk_assessment: str = Field(..., description="Risiko for kriminalitet")
    dd_risk_assessment: str = Field(..., description="Menneskerettighetsrisiko")  # NYE!
    social_dumping_risk: str = Field(..., description="Sosial dumping-risiko")
```

### Steg 2: Oppdater Oslomodell Agent
```python
# I src/specialists/oslomodell_agent_refactored.py - oppdater prompt:
"""
Inkluder også:
- crime_risk_assessment: "høy"/"moderat"/"lav"
- dd_risk_assessment: "høy"/"moderat"/"lav"           # NYE! Human rights due diligence
- social_dumping_risk: "høy"/"moderat"/"lav"
- subcontractor_levels: 0-2 basert på risiko
- apprenticeship_requirement: Strukturert objekt
- due_diligence_requirement: "A"/"B"/"Ikke påkrevd"
"""
```

### Steg 3: Oppdater Document Generator
```python
# Endre klassenavn i src/tools/oslomodell_document_generator.py
class OsloModelDocumentGenerator:  # var: OslomodellDocumentGenerator
    """
    Generates structured documents based on Oslo Model assessments.
    """
```

### Steg 4: Oppdater Comments i Scripts
```bash
# I scripts/deployment/deploy_dynamic_system.sh
echo "Starting specialist services..."
# Use -m to run modules from project root

echo "Waiting for services to start..."
# Run database migration (COMMENTED OUT)  
# Test that everything works
```

### Steg 5: Sjekk Gateway Service Catalog
Verifiser at alle RPC-metoder bruker engelske navn:
```sql
-- Skal være:
'database.create_procurement'
'database.save_triage_result'
'agent.run_triage'
'agent.run_oslomodell'
'agent.run_miljokrav'  -- Ikke run_miljokrav_agent
```

## 🧪 Testing

### Test Datamodeller
```python
# Test at enum fungerer
from src.models.procurement_models import RequirementCategory
print(RequirementCategory.INTEGRITY_REQUIREMENTS)  # Should print "seriøsitet"
print(RequirementCategory.DUE_DILIGENCE)          # Should print "aktsomhet"
```

### Test Agent med ny parameter
```python
# Test at dd_risk_assessment inkluderes i resultat
result = await oslomodell_agent.assess_procurement(request)
assert 'dd_risk_assessment' in result
assert result['dd_risk_assessment'] in ['høy', 'moderat', 'lav']
```

### Test Import Names
```python
# Test at alle imports fungerer med nye navn
from src.tools.oslomodell_document_generator import OsloModelDocumentGenerator
generator = OsloModelDocumentGenerator()
```

## ⚠️ Viktige Påminnelser

1. **User-facing verdier forblir norske**: `"seriøsitet"`, `"lærlinger"`, etc.
2. **Kun kode-identifikatorer endres**: enum keys, class names, method names
3. **Cache må tømmes**: Etter endringer, restart gateway og tøm cache
4. **dd_risk_assessment er ny**: Må legges til i prompts og datamodeller
5. **Test thoroughly**: Alle agenter må fortsatt fungere etter endringer

## 📊 Oppsummering av Endringer

| Type | Før | Etter |
|------|-----|-------|
| Enum Key | `SERIOSITET` | `INTEGRITY_REQUIREMENTS` |
| Enum Key | `AKTSOMHET` | `DUE_DILIGENCE` |
| Enum Key | `LARLINGER` | `APPRENTICES` |
| Enum Key | `MILJO` | `ENVIRONMENT` |
| Class | `OslomodellDocumentGenerator` | `OsloModelDocumentGenerator` |
| Parameter | N/A | `dd_risk_assessment` (ny) |
| Method | `vurder_anskaffelse` | `assess_procurement` |
| Method | `process_anskaffelse` | `process_procurement` |

**Estimert tid:** 2-3 timer for full implementering og testing