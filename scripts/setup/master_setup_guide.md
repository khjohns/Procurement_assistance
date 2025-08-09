# 🚀 Master Setup Guide - Komplett Procurement Assistant

## 📋 Oversikt
Denne guiden setter opp hele Procurement Assistant systemet med alle komponenter i riktig rekkefølge.

**Inkluderer:**
- Core database (procurements, triage, protocols)
- Oslomodell agent (integrity requirements)
- Miljøkrav agent (environmental requirements)
- Gateway services og ACL
- Språkvask (engelsk kode-konvensjoner)

## ⚡ Quick Start (10 min)

### 1. Sjekk Prerequisites (1 min)
```bash
# Sjekk at alt er på plass
python scripts/setup/run_db_setup.py check

# Forventet output:
# ✅ Directory found: /path/to/src/specialists
# ✅ Key file found: /path/to/gateway/main.py
# ✅ Prerequisites check completed.
```

### 2. Komplett Database Setup (3 min)
```bash
# Kjør konsolidert setup (erstatter alle fragmenterte scripts)
python scripts/setup/run_db_setup.py setup

# Forventet output:
# ✅ COMPLETE DATABASE SETUP SUCCESSFUL!
# Ready for: Triage, Oslomodell, Miljokrav agents.
```

### 3. Last Knowledge Bases (3 min)
```bash
# Last Oslomodell knowledge
python scripts/load_oslomodell_knowledge.py

# Last Miljøkrav knowledge  
python scripts/load_miljokrav_knowledge.py

# Forventet output for begge:
# ✅ Successfully stored document xxx-001
# ✅ Successfully stored document xxx-002
# ... (10+ dokumenter hver)
```

### 4. Implementer Språkvask (2 min)
Se [Språkvask Guide](#-språkvask-implementering) nedenfor for detaljerte endringer.

### 5. Start Gateway (1 min)
```bash
cd gateway
python main.py

# Forventet output:
# ✅ Service catalog loaded: 11 functions
# ✅ ACL config loaded: 25+ rules
# Gateway started on http://localhost:8000
```

### 6. Verifiser Alt Fungerer (1 min)
```bash
# Kjør komplett verifikasjon
python scripts/setup/run_db_setup.py verify

# Test med integrasjonstest
python tests/integration/test_triage_orchestration.py

# Forventet output:
# ✅ EXCELLENT - All systems ready!
# ✅ Orchestration completed and key actions were performed.
```

## 🧹 Språkvask Implementering

### Kritiske Endringer

**1. Oppdater Procurement Models**
```python
# I src/models/procurement_models_refactored.py
class RequirementCategory(str, Enum):
    INTEGRITY_REQUIREMENTS = "seriøsitet"    # var: SERIOSITET
    DUE_DILIGENCE = "aktsomhet"              # var: AKTSOMHET  
    APPRENTICES = "lærlinger"                # var: LARLINGER
    ENVIRONMENT = "miljø"                    # var: MILJO
    CLIMATE = "klima"                        # OK
    TRANSPORT = "transport"                  # OK
    DOCUMENTATION = "dokumentasjon"          # var: DOKUMENTASJON
    OTHER = "annet"                          # OK

class OslomodellAssessmentResult(BaseAssessmentResult):
    # Legg til NY parameter:
    crime_risk_assessment: str = Field(..., description="Risiko for kriminalitet")
    dd_risk_assessment: str = Field(..., description="Menneskerettighetsrisiko")  # NYE!
    social_dumping_risk: str = Field(..., description="Sosial dumping-risiko")
```

**2. Oppdater Oslomodell Agent Prompt**
```python
# I src/specialists/oslomodell_agent_refactored.py
"""
Inkluder også:
- crime_risk_assessment: "høy"/"moderat"/"lav"        # var: risk_assessment_akrim
- dd_risk_assessment: "høy"/"moderat"/"lav"           # NYE! Human rights due diligence  
- social_dumping_risk: "høy"/"moderat"/"lav"          # var: risk_assessment_social_dumping
"""
```

**3. Oppdater Document Generator**
```python
# I src/tools/oslomodell_document_generator.py
class OsloModelDocumentGenerator:  # var: OslomodellDocumentGenerator
    """
    Generates structured documents based on Oslo Model assessments.
    """
```

## 📁 Filstruktur Etter Setup

```
scripts/setup/
├── run_db_setup.py              # ✅ Konsoliderad setup script
├── complete_database_setup.sql  # ✅ Komplett SQL setup
├── verify_database.sql          # ✅ Komplett verifikasjon
└── README.md                    # Oppdateres

scripts/ (fragmenterte filer som nå kan fjernes)
├── complete_oslomodell_setup.sql     # ❌ Erstattes av complete_database_setup.sql  
├── setup_miljokrav_database.sql      # ❌ Erstattes av complete_database_setup.sql
└── load_*_knowledge.py               # ✅ Beholdes (kjøres etter database setup)

src/models/
├── procurement_models_refactored.py  # ✅ Oppdateres med språkvask
└── procurement_models.py             # ❌ Gammel fil, kan fjernes etter migrering

gateway/
└── main.py                           # ✅ Allerede korrekt

tests/integration/
├── test_triage_orchestration.py      # ✅ Test core functionality  
├── test_full_miljokrav_integration.py # ✅ Test miljøkrav
└── test_oslomodell_integration.py    # ✅ Test oslomodell
```

## 🧪 Testing Matrix

| Test | Beskrivelse | Kommando | Forventet Resultat |
|------|-------------|----------|-------------------|
| **Prerequisites** | Sjekk filer og struktur | `python scripts/setup/run_db_setup.py check` | ✅ Prerequisites check completed |
| **Database Setup** | Komplett setup | `python scripts/setup/run_db_setup.py setup` | ✅ COMPLETE DATABASE SETUP SUCCESSFUL |
| **Database Verify** | Verifiser setup | `python scripts/setup/run_db_setup.py verify` | ✅ EXCELLENT - All systems ready |
| **Knowledge Load** | Last knowledge bases | `python scripts/load_*_knowledge.py` | ✅ Successfully stored document |
| **Gateway Start** | Start gateway | `cd gateway && python main.py` | Gateway started on localhost:8000 |
| **Integration** | Test hele systemet | `python tests/integration/test_*` | ✅ Orchestration completed |

## 🚨 Feilsøking

### Problem: "Extension vector does not exist"
**Løsning:** Sørg for at pgvector er installert i PostgreSQL:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Problem: "Table already exists"
**Løsning:** Kjør cleanup først:
```bash
python scripts/setup/run_db_setup.py setup  # Inkluderer cleanup automatisk
```

### Problem: "Function ikke funnet i gateway"
**Løsning:** Restart gateway etter database endringer:
```bash
cd gateway
python main.py  # Laster service catalog på nytt
```

### Problem: "No knowledge results"
**Løsning:** Sjekk at knowledge er lastet:
```bash
python scripts/setup/run_db_setup.py verify
# Sjekk "DATA COUNT CHECK" seksjonen
```

### Problem: "Import error for dd_risk_assessment"
**Løsning:** Implementer språkvask først, deretter restart alle tjenester.

## ✅ Slutt Sjekkliste

**Database:**
- [ ] Prerequisites check passert
- [ ] Complete database setup kjørt
- [ ] Verification viser "EXCELLENT" status
- [ ] Knowledge bases lastet (oslomodell + miljokrav)

**Språkvask:**
- [ ] RequirementCategory enum oppdatert til engelsk
- [ ] dd_risk_assessment lagt til i OslomodellAssessmentResult
- [ ] Oslomodell agent prompt oppdatert
- [ ] Document generator klassenavn endret

**System:**
- [ ] Gateway startet uten feil
- [ ] ACL rules lastet (25+ rules)
- [ ] Service catalog lastet (11+ functions)
- [ ] Integration tests bestått

**Agents:**
- [ ] Triage agent fungerer
- [ ] Oslomodell agent fungerer (med dd_risk_assessment)
- [ ] Miljøkrav agent fungerer
- [ ] Orchestrator koordinerer alle agents

## 🎯 Suksess Kriterier

Systemet er klart når:
1. **`python scripts/setup/run_db_setup.py verify`** viser "✅ EXCELLENT"
2. **Gateway** starter uten feil og laster 11+ functions
3. **Integration tester** består for alle agents
4. **Språkvask** er implementert (engelsk kode, norsk user content)
5. **dd_risk_assessment** er tilgjengelig i Oslomodell resultater

**Estimert total tid:** 10-15 minutter for fresh setup, 5 minutter for språkvask på eksisterende system.