# 📊 Ingester Tools - Formål og Funksjoner

## 🎯 Oversikt

To komplementære verktøy for å importere data fra CSV-filer til Procurement Assistant systemet:

| Tool | Formål | Target | RPC Methods |
|------|--------|--------|-------------|
| **knowledge_ingester.py** | Knowledge bases med AI search | Vector databases | `store_knowledge_document`, `store_miljokrav_document` |
| **document_ingester.py** | Strukturerte business data | Vanlige tabeller | `insert_requirement`, `upsert_supplier`, osv. |

## 🧠 Knowledge Ingester

**Formål**: Import av dokumenter til AI-søkbare knowledge bases med embeddings.

### Hovedfunksjoner:
- **Chunking**: Automatisk oppdeling av lange dokumenter
- **Embedding generering**: Via RPC Gateway til AI-tjenester
- **Metadata extraktion**: Fleksibel mapping fra CSV kolonner
- **Multiple knowledge bases**: Oslomodell, Miljøkrav, eller custom

### Bruksområder:
- Regelverk og forskrifter (Oslomodell)
- Miljøinstrukser og retningslinjer
- Kontraktsmaler og standardtekster
- FAQ og veiledningsdokumenter

### Typisk workflow:
```
CSV Row → Content Processing → Chunking → Embedding → Vector Storage
```

### Eksempel konfigurasjon:
```yaml
knowledge_base: "oslomodell"
rpc_method: "database.store_knowledge_document"
csv_mapping:
  id_column: "krav_id"
  content_column: "beskrivelse"
  metadata_columns: ["kategori", "kilde", "versjon"]
chunking:
  enabled: true
  size: 1000
  overlap: 100
```

## 📄 Document Ingester

**Formål**: Import av strukturerte forretningsdata til vanlige database-tabeller.

### Hovedfunksjoner:
- **Type konvertering**: String → int/float/boolean/date/json
- **Datavalidering**: Built-in og custom validators
- **Batch processing**: Effektiv import av store datasett
- **Upsert support**: Oppdatering av eksisterende poster

### Bruksområder:
- Requirements og regelkrav (SQL eksempel fra oppgaven)
- Leverandørregistre
- Kontraktsdata
- Kategoriklassifikasjoner

### Typisk workflow:
```
CSV Row → Field Mapping → Type Conversion → Validation → RPC Storage
```

### Eksempel konfigurasjon:
```yaml
target:
  table_name: "requirements"
  rpc_method: "database.insert_requirement"
  batch_size: 50
field_mappings:
  - csv_column: "Kode"
    db_field: "code"
    data_type: "string"
    required: true
    validator: "valid_code"
  - csv_column: "Navn"
    db_field: "name"
    data_type: "string"
    transformer: "trim"
  - csv_column: "Verdi"
    db_field: "value"
    data_type: "integer"
    validator: "positive_number"
```

## 🔧 Felles Funksjoner

Begge verktøy har:

### Smart CSV Handling:
- **Auto-detect delimiter**: Komma, semikolon, tab, pipe
- **Header cleaning**: Trim whitespace, handle encoding
- **Robust parsing**: Håndterer sitater, escape characters

### Fleksibel Konfigurasjon:
- **YAML-basert**: Gjenbrukbare konfigurasjonsfiler
- **Environment-aware**: .env support for credentials
- **Dry-run mode**: Test uten å lagre data

### Error Handling:
- **Continue on error**: Skip bad rows, continue processing
- **Detaljert logging**: Structured logs med statistikk
- **Batch failure handling**: Isoler feil til enkelte poster

### Performance:
- **Async RPC**: Non-blocking database calls
- **Batch processing**: Reduserer network overhead
- **Progress tracking**: Real-time status updates

## 📋 Bruksscenarier

### Scenario 1: Import av Oslomodell Requirements
```bash
# 1. Forbered CSV med kolonner: krav_id, navn, beskrivelse, kategori
# 2. Opprett oslomodell_config.yaml
# 3. Kjør import
python src/tools/knowledge_ingester.py \
  --config configs/oslomodell_config.yaml \
  --csv data/oslomodell_krav.csv
```

### Scenario 2: Import av Leverandører
```bash
# 1. Forbered CSV med kolonner: org_nr, navn, adresse, kontakt
# 2. Opprett suppliers_config.yaml  
# 3. Kjør import
python src/tools/document_ingester.py \
  --config configs/suppliers_config.yaml \
  --csv data/leverandorer.csv
```

### Scenario 3: Masseoppdatering av Requirements
```bash
# SQL-til-CSV eksport fra eksisterende system
# → CSV med requirements data
# → document_ingester med upsert=true
python src/tools/document_ingester.py \
  --config configs/requirements_upsert_config.yaml \
  --csv data/requirements_update.csv
```

## 🎛️ Konfigurasjon Templates

Verktøyene kan leveres med eksempel-konfigurasjoner:

```
configs/
├── oslomodell_knowledge.yaml
├── miljokrav_knowledge.yaml
├── requirements_insert.yaml
├── suppliers_upsert.yaml
└── contracts_batch.yaml
```

## 🔄 Integrasjon med Eksisterende System

### Knowledge Ingester → AI Agents:
- Oslomodell Agent bruker `search_knowledge_documents`
- Miljøkrav Agent bruker `search_miljokrav_documents`
- Orchestrator kan søke på tvers av knowledge bases

### Document Ingester → Business Logic:
- Requirements tilgjengelig for alle agents
- Leverandørdata for due diligence vurderinger
- Kontraktsdata for automated protokoll generering

## 📊 Monitoring og Statistikk

Begge verktøy returnerer detaljert statistikk:

```python
{
    'total_rows': 1000,
    'processed_rows': 995,
    'stored_records': 990,
    'failed_records': 5,
    'processing_time': '00:02:30'
}
```

Dette muliggjør:
- **Quality assurance**: Identifiser problematiske data
- **Performance tuning**: Optimaliser batch-størrelser
- **Error tracking**: Følg opp feilede imports

## 🚀 Fremtidige Utvidelser

Potensielle forbedringer:
- **Excel support**: Direkte .xlsx import
- **Database sync**: Incremental updates fra eksterne systemer
- **Data profiling**: Automatisk analyse av CSV-struktur
- **Custom validators**: Plugin-system for domain-spesifikk validering
- **Progress webhooks**: Real-time status til web UI