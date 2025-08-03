# GEMINI_QUALITY_ASSURANCE.md - Kontinuerlig Kvalitetssikring og Standarder

## Oversikt

Dette dokumentet definerer hvordan Gemini CLI skal opptre som en **proaktiv kvalitetsvokter** som kontinuerlig sikrer at Anskaffelsesassistenten følger beste praksis for struktur, testing, dokumentasjon og vedlikehold.

## Grunnleggende direktiver for Gemini CLI

### ALLTID når du arbeider med koden:

1. **Sjekk mappestruktur** - Er filen på rett sted?
2. **Krev tester** - Finnes det tester for denne funksjonen?
3. **Oppdater dokumentasjon** - Er API-docs, README og diagrammer oppdatert?
4. **Logg beslutninger** - Trengs det en ADR for denne endringen?
5. **Spor endringer** - Er CHANGELOG.md oppdatert?

## 1. Standard Mappestruktur

### Komplett prosjektstruktur

```
anskaffelsesassistenten/
├── src/                              # All produksjonskode
│   ├── orchestrators/                # Nivå 2: Orkestrering
│   │   ├── __init__.py
│   │   ├── base_orchestrator.py
│   │   ├── procurement_orchestrator.py
│   │   ├── reasoning_orchestrator.py
│   │   └── README.md
│   ├── specialists/                  # Nivå 3: Spesialistagenter
│   │   ├── __init__.py
│   │   ├── base_specialist.py
│   │   ├── triage/
│   │   │   ├── __init__.py
│   │   │   ├── triage_agent.py
│   │   │   └── triage_prompts.py
│   │   ├── protocol/
│   │   │   ├── __init__.py
│   │   │   ├── protocol_generator.py
│   │   │   └── protocol_templates.py
│   │   ├── oslomodell/
│   │   │   ├── __init__.py
│   │   │   ├── oslomodell_agent.py
│   │   │   └── oslomodell_rules.py
│   │   └── README.md
│   ├── tools/                        # Nivå 4: Verktøy/Gateways
│   │   ├── __init__.py
│   │   ├── gateways/
│   │   │   ├── __init__.py
│   │   │   ├── rpc_gateway_client.py
│   │   │   ├── gemini_gateway.py
│   │   │   ├── embedding_gateway.py
│   │   │   └── base_gateway.py
│   │   ├── registry/
│   │   │   ├── __init__.py
│   │   │   ├── agent_registry.py
│   │   │   └── tool_registry.py
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── retry_handler.py
│   │   │   ├── validators.py
│   │   │   └── monitoring.py
│   │   └── README.md
│   ├── models/                       # Datamodeller
│   │   ├── __init__.py
│   │   ├── procurement_models.py
│   │   ├── agent_models.py
│   │   └── gateway_models.py
│   ├── config/                       # Konfigurasjon
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── logging_config.py
│   │   └── constants.py
│   └── main.py                      # Hovedinngang
│
├── gateway/                          # RPC Gateway (separat tjeneste)
│   ├── src/
│   │   ├── main.py
│   │   ├── middleware/
│   │   ├── handlers/
│   │   └── utils/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── tests/                            # Alle tester
│   ├── unit/                        # Enhetstester
│   │   ├── orchestrators/
│   │   │   ├── test_procurement_orchestrator.py
│   │   │   └── test_reasoning_orchestrator.py
│   │   ├── specialists/
│   │   │   ├── test_triage_agent.py
│   │   │   ├── test_protocol_generator.py
│   │   │   └── test_oslomodell_agent.py
│   │   ├── tools/
│   │   │   ├── test_rpc_gateway_client.py
│   │   │   ├── test_gemini_gateway.py
│   │   │   └── test_embedding_gateway.py
│   │   └── models/
│   │       └── test_procurement_models.py
│   ├── integration/                  # Integrasjonstester
│   │   ├── test_full_workflow.py
│   │   ├── test_gateway_integration.py
│   │   ├── test_database_operations.py
│   │   └── test_llm_integration.py
│   ├── e2e/                         # End-to-end tester
│   │   ├── test_procurement_journey.py
│   │   └── test_error_scenarios.py
│   ├── fixtures/                    # Test data og mocks
│   │   ├── sample_requests.json
│   │   ├── mock_responses.py
│   │   └── test_embeddings.npy
│   ├── conftest.py                  # Pytest konfigurasjon
│   └── README.md
│
├── docs/                            # All dokumentasjon
│   ├── api/                        # API dokumentasjon
│   │   ├── openapi.yaml
│   │   ├── postman_collection.json
│   │   └── api_examples.md
│   ├── architecture/               # Arkitekturdokumentasjon
│   │   ├── diagrams/
│   │   │   ├── system_overview.mmd
│   │   │   ├── data_flow.mmd
│   │   │   ├── deployment.mmd
│   │   │   └── README.md
│   │   ├── decisions/              # ADR (Architecture Decision Records)
│   │   │   ├── ADR-001-rpc-gateway.md
│   │   │   ├── ADR-002-dynamic-orchestration.md
│   │   │   ├── ADR-003-embedding-strategy.md
│   │   │   └── ADR-template.md
│   │   └── patterns/
│   │       ├── agent-pattern.md
│   │       └── gateway-pattern.md
│   ├── guides/                     # Brukerveiledninger
│   │   ├── getting-started.md
│   │   ├── deployment-guide.md
│   │   ├── configuration-guide.md
│   │   └── troubleshooting.md
│   ├── development/                # Utviklerdokumentasjon
│   │   ├── contributing.md
│   │   ├── code-style.md
│   │   ├── testing-strategy.md
│   │   └── release-process.md
│   └── CHANGELOG.md
│
├── scripts/                        # Utility scripts
│   ├── setup/
│   │   ├── init_database.py
│   │   ├── create_indexes.sql
│   │   └── seed_data.py
│   ├── maintenance/
│   │   ├── rotate_credentials.py
│   │   ├── backup_database.py
│   │   └── health_check.py
│   ├── deployment/
│   │   ├── deploy.sh
│   │   ├── rollback.sh
│   │   └── smoke_test.py
│   └── development/
│       ├── generate_api_docs.py
│       ├── update_diagrams.py
│       └── lint_and_format.sh
│
├── infrastructure/                 # Infrastructure as Code
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── kubernetes/
│   │   ├── deployments/
│   │   ├── services/
│   │   └── configmaps/
│   └── docker/
│       ├── Dockerfile.app
│       ├── Dockerfile.gateway
│       └── docker-compose.yml
│
├── .github/                       # GitHub Actions
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── cd.yml
│   │   ├── security-scan.yml
│   │   └── documentation.yml
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── monitoring/                    # Monitoring og alerting
│   ├── prometheus/
│   │   └── alerts.yml
│   ├── grafana/
│   │   └── dashboards/
│   └── logs/
│       └── log_patterns.json
│
├── .env.example                  # Eksempel miljøvariabler
├── .gitignore
├── requirements.txt              # Python dependencies
├── requirements-dev.txt          # Development dependencies
├── pytest.ini                    # Pytest konfigurasjon
├── pyproject.toml               # Python prosjekt konfig
├── Makefile                     # Vanlige kommandoer
├── README.md                    # Hovedinformasjon
└── LICENSE
```

## 2. Testing Standards

### 2.1 Test Naming Convention

```python
# Enhetstester: test_<function_name>_<scenario>_<expected_result>.py
test_vurder_anskaffelse_high_value_returns_red.py
test_lagre_resultat_invalid_color_raises_error.py

# Integrasjonstester: test_integration_<component>_<component>.py
test_integration_orchestrator_gateway.py
test_integration_triage_database.py

# E2E tester: test_e2e_<user_journey>.py
test_e2e_complete_procurement_workflow.py
test_e2e_manual_review_process.py
```

### 2.2 Test Coverage Requirements

**Minimum coverage**: 80% total, 90% for kritiske komponenter

```yaml
# .coveragerc
[run]
source = src/
omit = 
    */tests/*
    */migrations/*
    */__init__.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
```

### 2.3 Kritiske Test Scenarios

```python
# tests/critical/test_security_operations.py
import pytest
from scripts.maintenance import rotate_credentials

class TestSecurityOperations:
    """Tester for sikkerhetskritiske operasjoner"""
    
    @pytest.mark.critical
    async def test_database_password_rotation(self, test_db):
        """Test at passordrotasjon fungerer uten nedetid"""
        old_password = test_db.get_current_password()
        
        # Utfør rotasjon
        result = await rotate_credentials.rotate_database_password()
        
        # Verifiser
        assert result.success
        assert test_db.get_current_password() != old_password
        assert test_db.can_connect()
        assert result.downtime_seconds < 1.0
    
    @pytest.mark.critical
    async def test_api_key_rotation_preserves_active_sessions(self):
        """Test at API-nøkkel rotasjon ikke bryter aktive sesjoner"""
        # ... implementasjon ...
```

## 3. API Dokumentasjon

### 3.1 OpenAPI Specification

```yaml
# docs/api/openapi.yaml
openapi: 3.0.3
info:
  title: Anskaffelsesassistenten API
  version: 1.0.0
  description: |
    API for intelligent håndtering av offentlige anskaffelser.
    
    ## Autentisering
    Alle requests krever `X-Agent-ID` header.
    
    ## Rate Limiting
    - 60 requests per minutt per agent
    - 429 Too Many Requests ved overskridelse

servers:
  - url: https://api.anskaffelse.oslo.kommune.no/v1
    description: Production
  - url: https://staging-api.anskaffelse.oslo.kommune.no/v1
    description: Staging

paths:
  /rpc:
    post:
      summary: Execute RPC method
      operationId: executeRpc
      tags:
        - RPC
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JsonRpcRequest'
            examples:
              triageRequest:
                summary: Lagre triageresultat
                value:
                  jsonrpc: "2.0"
                  method: "database.lagre_triage_resultat"
                  params:
                    request_id: "123e4567-e89b-12d3-a456-426614174000"
                    farge: "GRØNN"
                    begrunnelse: "Lav verdi og kompleksitet"
                    confidence: 0.95
                  id: 1
      responses:
        '200':
          description: Successful RPC execution
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JsonRpcResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '429':
          $ref: '#/components/responses/RateLimited'

components:
  schemas:
    JsonRpcRequest:
      type: object
      required:
        - jsonrpc
        - method
      properties:
        jsonrpc:
          type: string
          enum: ["2.0"]
        method:
          type: string
          pattern: '^[a-z]+\.[a-z_]+$'
        params:
          type: object
        id:
          type: integer
```

### 3.2 Postman Collection

```json
{
  "info": {
    "name": "Anskaffelsesassistenten",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Triage Operations",
      "item": [
        {
          "name": "Save Triage Result",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "X-Agent-ID",
                "value": "{{agent_id}}"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"jsonrpc\": \"2.0\",\n  \"method\": \"database.lagre_triage_resultat\",\n  \"params\": {\n    \"request_id\": \"{{request_id}}\",\n    \"farge\": \"GRØNN\",\n    \"begrunnelse\": \"Test triage\",\n    \"confidence\": 0.95\n  },\n  \"id\": 1\n}"
            },
            "url": {
              "raw": "{{base_url}}/rpc",
              "host": ["{{base_url}}"],
              "path": ["rpc"]
            }
          }
        }
      ]
    }
  ],
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000"
    },
    {
      "key": "agent_id",
      "value": "anskaffelsesassistenten"
    }
  ]
}
```

## 4. Arkitekturdiagrammer

### 4.1 Mermaid Diagrammer

```mermaid
# docs/architecture/diagrams/system_overview.mmd
graph TB
    subgraph "Frontend Layer"
        UI[Web UI]
        CLI[CLI Interface]
    end
    
    subgraph "Orchestration Layer"
        PO[Procurement Orchestrator]
        RO[Reasoning Orchestrator]
    end
    
    subgraph "Specialist Layer"
        TA[Triage Agent]
        PG[Protocol Generator]
        OA[Oslomodell Agent]
    end
    
    subgraph "Gateway Layer"
        RGW[RPC Gateway]
        GGW[Gemini Gateway]
        EGW[Embedding Gateway]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL)]
        CACHE[(Redis)]
        S3[Object Storage]
    end
    
    UI --> PO
    CLI --> RO
    PO --> TA
    PO --> PG
    RO --> TA
    RO --> PG
    RO --> OA
    TA --> GGW
    PG --> GGW
    OA --> EGW
    TA --> RGW
    PG --> RGW
    RGW --> DB
    EGW --> DB
    RGW --> CACHE
```

### 4.2 Auto-generering av diagrammer

```python
# scripts/development/update_diagrams.py
import os
from pathlib import Path
import subprocess

def generate_diagrams():
    """Genererer PNG/SVG fra Mermaid filer"""
    diagram_dir = Path("docs/architecture/diagrams")
    output_dir = Path("docs/architecture/images")
    output_dir.mkdir(exist_ok=True)
    
    for mmd_file in diagram_dir.glob("*.mmd"):
        output_file = output_dir / f"{mmd_file.stem}.png"
        cmd = [
            "mmdc",
            "-i", str(mmd_file),
            "-o", str(output_file),
            "-t", "dark",
            "-b", "transparent"
        ]
        subprocess.run(cmd, check=True)
        print(f"Generated: {output_file}")

if __name__ == "__main__":
    generate_diagrams()
```

## 5. Architecture Decision Records (ADR)

### 5.1 ADR Template

```markdown
# ADR-XXX: [Kort beskrivende tittel]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-YYY]

## Context
Hva er problemet vi prøver å løse? Hvilke krefter påvirker beslutningen?

## Decision
Hva har vi besluttet å gjøre?

## Consequences
### Positive
- Hvilke fordeler får vi?

### Negative
- Hvilke ulemper må vi leve med?

### Risks
- Hvilke risikoer introduserer denne beslutningen?

## Alternatives Considered
1. **Alternativ 1**: Beskrivelse og hvorfor det ble forkastet
2. **Alternativ 2**: Beskrivelse og hvorfor det ble forkastet

## References
- [Link til relevant dokumentasjon]
- [Link til diskusjon/issue]
```

### 5.2 Eksempel ADR

```markdown
# ADR-001: Bruk av RPC Gateway for database-tilgang

## Status
Accepted

## Context
Vi trenger en sikker, skalerbar måte å håndtere database-tilgang på tvers av flere agenter. 
Direkte SQL fra agenter gir sikkerhetsrisikoer og vanskeliggjør tilgangskontroll.

## Decision
Implementere en RPC Gateway som eksponerer database-operasjoner som JSON-RPC metoder 
med sentralisert ACL og rate limiting.

## Consequences
### Positive
- Eliminerer SQL injection risiko
- Sentralisert tilgangskontroll
- Enkel audit logging
- Bedre ytelsesovervåking

### Negative
- Ekstra kompleksitet i arkitekturen
- Potensiell flaskehals
- Mer kode å vedlikeholde

### Risks
- Gateway blir single point of failure
- Mitigation: Implementer HA med flere instanser

## Alternatives Considered
1. **Direct SQL**: For risikabelt, vanskelig å kontrollere
2. **GraphQL**: Overkill for vårt use case, mer komplekst
3. **REST API**: Mindre fleksibelt enn RPC for våre behov
```

## 6. Changelog Management

### 6.1 CHANGELOG.md Format

```markdown
# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Dynamisk orkestrering med ReasoningOrchestrator
- Verktøy-discovery endepunkt i RPC Gateway

### Changed
- Migrert fra SimpleSupabaseGateway til RPCGatewayClient

### Fixed
- pgbouncer prepared statement håndtering

## [1.2.0] - 2025-08-02
### Added
- RPC Gateway implementasjon
- Comprehensive test suite
- API dokumentasjon med OpenAPI

### Security
- Implementert rate limiting
- Lagt til ACL for agent-tilgang

## [1.1.0] - 2025-07-15
### Added
- ProtocolGenerator spesialist
- Embedding gateway for RAG
```

### 6.2 Auto-generering av changelog

```python
# scripts/development/update_changelog.py
import subprocess
from datetime import datetime

def generate_changelog_entry():
    """Generer changelog entry basert på git commits"""
    # Hent commits siden siste tag
    last_tag = subprocess.check_output(
        ["git", "describe", "--tags", "--abbrev=0"]
    ).decode().strip()
    
    commits = subprocess.check_output([
        "git", "log", f"{last_tag}..HEAD", 
        "--pretty=format:%s", "--reverse"
    ]).decode().split('\n')
    
    # Kategoriser commits
    added, changed, fixed, security = [], [], [], []
    
    for commit in commits:
        if commit.startswith("feat:"):
            added.append(commit[5:].strip())
        elif commit.startswith("fix:"):
            fixed.append(commit[4:].strip())
        elif commit.startswith("security:"):
            security.append(commit[9:].strip())
        elif commit.startswith("refactor:") or commit.startswith("perf:"):
            changed.append(commit.split(":", 1)[1].strip())
    
    # Generer markdown
    print(f"\n## [Unreleased] - {datetime.now().strftime('%Y-%m-%d')}")
    
    if added:
        print("### Added")
        for item in added:
            print(f"- {item}")
    # ... etc
```

## 7. Proaktive Sjekklister for Gemini CLI

### 7.1 Pre-commit sjekkliste

Før hver commit, skal Gemini CLI sjekke:

```python
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-structure
        name: Verify project structure
        entry: python scripts/development/check_structure.py
        language: python
        
      - id: test-coverage
        name: Ensure test coverage
        entry: pytest --cov=src --cov-report=term-missing --cov-fail-under=80
        language: python
        
      - id: update-docs
        name: Update API documentation
        entry: python scripts/development/generate_api_docs.py
        language: python
        
      - id: security-scan
        name: Security vulnerability scan
        entry: bandit -r src/
        language: python
```

### 7.2 Kontinuerlige sjekker

```python
# scripts/development/continuous_checks.py
"""
Kjøres av Gemini CLI ved hver betydelig endring
"""

import os
from pathlib import Path

class QualityChecker:
    def __init__(self, project_root):
        self.root = Path(project_root)
    
    def check_all(self):
        """Kjør alle kvalitetssjekker"""
        results = {
            "structure": self.check_structure(),
            "tests": self.check_test_coverage(),
            "docs": self.check_documentation(),
            "security": self.check_security(),
            "changelog": self.check_changelog()
        }
        
        return all(results.values())
    
    def check_structure(self):
        """Verifiser at mappestrukturen følger standard"""
        required_dirs = [
            "src/orchestrators",
            "src/specialists", 
            "src/tools",
            "tests/unit",
            "tests/integration",
            "docs/api",
            "docs/architecture/decisions"
        ]
        
        for dir_path in required_dirs:
            if not (self.root / dir_path).exists():
                print(f"❌ Missing required directory: {dir_path}")
                return False
        
        print("✅ Project structure is correct")
        return True
    
    def check_test_coverage(self):
        """Sjekk at nye filer har tilhørende tester"""
        src_files = set(self.root.glob("src/**/*.py"))
        test_files = set(self.root.glob("tests/**/*.py"))
        
        for src_file in src_files:
            if "__init__.py" in str(src_file):
                continue
                
            expected_test = f"test_{src_file.stem}.py"
            if not any(expected_test in str(t) for t in test_files):
                print(f"❌ Missing test for: {src_file}")
                return False
        
        print("✅ All source files have tests")
        return True
    
    def check_documentation(self):
        """Sjekk at dokumentasjon er oppdatert"""
        # Sjekk at OpenAPI spec finnes
        openapi = self.root / "docs/api/openapi.yaml"
        if not openapi.exists():
            print("❌ Missing OpenAPI specification")
            return False
        
        # Sjekk at README er oppdatert nylig
        readme = self.root / "README.md"
        if readme.stat().st_mtime < (time.time() - 30*24*60*60):  # 30 dager
            print("⚠️  README might be outdated")
        
        print("✅ Documentation exists")
        return True
```

## 8. Praktiske kommandoer (Makefile)

```makefile
# Makefile
.PHONY: help test lint docs deploy

help:
	@echo "Available commands:"
	@echo "  make test          - Run all tests"
	@echo "  make lint          - Run linting and formatting"
	@echo "  make docs          - Generate documentation"
	@echo "  make check         - Run all quality checks"
	@echo "  make deploy-staging - Deploy to staging"

# Testing
test:
	pytest tests/ -v --cov=src --cov-report=html

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v -m integration

test-critical:
	pytest tests/ -v -m critical

# Code quality
lint:
	black src/ tests/
	isort src/ tests/
	flake8 src/ tests/
	mypy src/

security:
	bandit -r src/
	safety check

# Documentation
docs:
	python scripts/development/generate_api_docs.py
	python scripts/development/update_diagrams.py
	mkdocs build

# Development
dev-setup:
	pip install -r requirements-dev.txt
	pre-commit install
	cp .env.example .env
	@echo "Remember to update .env with your values!"

# Quality checks
check: lint test security
	python scripts/development/continuous_checks.py

# Database
db-migrate:
	python scripts/setup/init_database.py
	psql -f scripts/setup/create_indexes.sql

db-seed:
	python scripts/setup/seed_data.py

# Deployment
deploy-staging:
	./scripts/deployment/deploy.sh staging
	python scripts/deployment/smoke_test.py staging

deploy-prod:
	@echo "Production deployment requires approval"
	./scripts/deployment/deploy.sh production --require-approval
	python scripts/deployment/smoke_test.py production
```

## 9. Git Hooks

### 9.1 Pre-commit hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Running pre-commit checks..."

# Check for sensitive data
if git diff --cached --name-only | xargs grep -E "(password|secret|key).*=.*['\"].*['\"]" 2>/dev/null; then
    echo "❌ Potential secrets detected in commit"
    exit 1
fi

# Run tests for changed files
changed_py_files=$(git diff --cached --name-only --diff-filter=ACM | grep "\.py$")
if [ -n "$changed_py_files" ]; then
    echo "Running tests for changed files..."
    pytest tests/ -v --timeout=10
fi

# Update documentation if needed
if git diff --cached --name-only | grep -E "(src/.*\.py|docs/)" > /dev/null; then
    echo "Updating documentation..."
    make docs
    git add docs/api/openapi.yaml
fi

echo "✅ Pre-commit checks passed"
```

## 10. Continuous Integration

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      
      - name: Run quality checks
        run: make check
      
      - name: Check project structure
        run: python scripts/development/continuous_checks.py
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
      
      - name: Build documentation
        run: make docs
      
      - name: Security scan
        run: |
          bandit -r src/
          safety check
```

## Konklusjon

Ved å følge denne guiden vil Gemini CLI fungere som en proaktiv kvalitetsvokter som:

1. **Håndhever struktur**: Konsistent mappeorganisering
2. **Krever testing**: Ingen kode uten tester
3. **Vedlikeholder dokumentasjon**: Alltid oppdatert API-docs og diagrammer
4. **Tracker beslutninger**: ADR for alle arkitekturvalg
5. **Logger endringer**: Detaljert CHANGELOG

Dette sikrer at Anskaffelsesassistenten utvikles med høyeste kvalitetsstandarder og forblir vedlikeholdbar over tid.