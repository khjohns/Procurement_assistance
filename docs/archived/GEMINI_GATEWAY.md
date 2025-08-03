# GEMINI.md - MCP JSON-RPC Library and Central Gateway Development

## Project Overview

This project implements a robust Model Context Protocol (MCP) communication infrastructure for an AI platform, consisting of:

1. **JSON-RPC Client Library**: A reusable Python library for MCP communication
2. **Central MCP Gateway**: A centralized service discovery and authorization gateway

### Architecture Vision

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   AI Agent  │────▶│  Central Gateway │────▶│ MCP Service │
└─────────────┘     └──────────────────┘     └─────────────┘
                            │
                    ┌───────┴────────┐
                    │Service Catalog │
                    │      (ACL)     │
                    └────────────────┘
```

## Core Components

### 1. JSON-RPC Client Library (`tools/json_rpc_client.py`)

**Current State:**
- ✅ Abstract transport layer (`JsonRpcTransport`)
- ✅ Generic JSON-RPC client with request/response handling
- ✅ MCP-specific client implementation
- ✅ Subprocess transport for local MCP servers
- ❌ HTTP/WebSocket transport (needs implementation)
- ❌ Resilience patterns (retry, circuit breaker)

**Key Classes:**
- `JsonRpcTransport`: Abstract base for all transports
- `JsonRpcClient`: Generic JSON-RPC 2.0 client
- `MCPClient`: MCP-specific client with protocol support
- `SubprocessTransport`: For local process communication

### 2. Central MCP Gateway (To Be Developed)

**Requirements:**
- Service discovery and registration
- Zero Trust authorization (ACL-based)
- Request routing and protocol translation
- High availability and horizontal scaling
- Comprehensive logging and monitoring

## Development Guidelines

### When Adding New Features

1. **Follow the Layered Architecture:**
   ```
   Transport Layer → JSON-RPC Layer → MCP Layer → Domain-Specific Wrappers
   ```

2. **Maintain Protocol Compatibility:**
   - Support multiple MCP protocol versions (currently: "0.1.0", "2024-11-05", "2025-06-18")
   - Use `ProtocolVersion` enum for version management

3. **Error Handling:**
   - Use structured logging with `structlog`
   - Implement proper timeout handling
   - Provide meaningful error messages

4. **Type Safety:**
   - Use type hints throughout
   - Create domain-specific wrappers (like `SupabaseMCPClient`)

### Priority Development Tasks

#### Task 1: Implement HttpTransport
Create `HttpTransport` class with:
- HTTP POST support for request/response
- WebSocket support for bidirectional communication
- Authentication (Bearer tokens, Managed Identity)
- Retry logic with exponential backoff
- Connection pooling

```python
class HttpTransport(JsonRpcTransport):
    def __init__(self, config: HttpTransportConfig):
        # Implementation needed
```

#### Task 2: Add Resilience Patterns
Implement:
- Circuit breaker pattern
- Retry with exponential backoff
- Timeout handling
- Connection health checks

#### Task 3: Create Gateway Foundation
Start with:
```python
class MCPGateway:
    def __init__(self):
        self.service_catalog = ServiceCatalog()
        self.acl_manager = ACLManager()
        self.router = RequestRouter()
```

### Testing Strategy

1. **Unit Tests:**
   - Mock transports for testing JSON-RPC logic
   - Test each protocol version separately
   
2. **Integration Tests:**
   - Test against real MCP servers (Supabase, filesystem)
   - Verify timeout and error handling

3. **Load Tests:**
   - Gateway must handle 1000+ concurrent connections
   - Measure latency under load

### Security Considerations

1. **Authentication:**
   - Support Azure Managed Identity
   - API key management
   - JWT token validation

2. **Authorization:**
   - Implement ACL checks in gateway
   - Per-agent tool permissions
   - Audit logging for all access

3. **Transport Security:**
   - TLS for all HTTP connections
   - Certificate validation
   - Secure token storage

### Code Style and Standards

1. **Python 3.10+ features:**
   - Use async/await throughout
   - Type hints with Optional, Union, etc.
   - Dataclasses for configuration

2. **Error Messages:**
   ```python
   logger.error("Failed to connect to MCP server",
               server=server_name,
               error=str(e),
               retry_count=attempts)
   ```

3. **Documentation:**
   - Docstrings for all public methods
   - Type hints for all parameters
   - Examples in docstrings

### Gateway Implementation Roadmap

#### Phase 1: Basic Gateway (MVP)
- [ ] Service registration API
- [ ] Simple routing based on tool name
- [ ] Basic ACL (allow/deny lists)
- [ ] Health check endpoints

#### Phase 2: Production Ready
- [ ] High availability (multiple instances)
- [ ] Load balancing
- [ ] Caching layer
- [ ] Comprehensive monitoring

#### Phase 3: Advanced Features
- [ ] Dynamic service discovery
- [ ] Protocol version negotiation
- [ ] Rate limiting and quotas
- [ ] Cost tracking for paid APIs

### Example Usage Patterns

#### For Library Users:
```python
# Simple usage
client = await MCPServerLauncher.launch_supabase(
    project_ref="xxx",
    access_token="xxx"
)
result = await client.call_tool("execute_sql", {"query": "SELECT 1"})

# With gateway
gateway_client = await create_gateway_client("https://mcp-gateway.internal")
tools = await gateway_client.list_tools()  # Only shows authorized tools
```

#### For Gateway Configuration:
```yaml
services:
  supabase:
    endpoint: "internal-supabase-mcp:8080"
    protocol_version: "2025-06-18"
    health_check: "/health"
    
acl:
  procurement-agent:
    allowed_tools:
      - supabase.execute_sql
      - filesystem.read_file
  finance-agent:
    allowed_tools:
      - supabase.execute_sql
```

### Performance Requirements

1. **Latency:**
   - Gateway overhead < 10ms
   - Connection establishment < 100ms

2. **Throughput:**
   - 10,000 requests/second per gateway instance
   - Horizontal scaling for higher loads

3. **Resource Usage:**
   - Memory < 512MB per gateway instance
   - CPU efficient with async I/O

### Monitoring and Observability

Implement metrics for:
- Request count by tool/agent
- Response times (p50, p95, p99)
- Error rates by type
- Active connections
- Token usage for LLM tools

Use OpenTelemetry for:
- Distributed tracing
- Metrics collection
- Log correlation

### Common Pitfalls to Avoid

1. **Don't block the event loop:**
   ```python
   # Bad
   time.sleep(1)
   
   # Good
   await asyncio.sleep(1)
   ```

2. **Handle connection failures gracefully:**
   - Always implement timeouts
   - Provide fallback behavior
   - Log errors with context

3. **Avoid memory leaks:**
   - Clean up pending requests on disconnect
   - Limit queue sizes
   - Implement connection pooling

### Questions for Gemini

When developing, ask Gemini about:
1. "How should I implement WebSocket reconnection logic in HttpTransport?"
2. "What's the best way to handle protocol version mismatch between client and server?"
3. "How can I implement efficient caching in the gateway without memory bloat?"
4. "What's the optimal circuit breaker configuration for MCP services?"

### References

- MCP Specification: https://modelcontextprotocol.io/docs
- JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
- Azure Managed Identity: https://docs.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/
- Circuit Breaker Pattern: https://martinfowler.com/bliki/CircuitBreaker.html

## Quick Start for New Developers

1. **Clone and setup:**
   ```bash
   git clone <repo>
   cd mcp-platform
   pip install -r requirements.txt
   ```

2. **Run tests:**
   ```bash
   pytest tests/
   ```

3. **Test with local MCP server:**
   ```python
   # See test_gateway.py for examples
   ```

4. **Start developing:**
   - Pick a task from "Priority Development Tasks"
   - Follow the architecture patterns
   - Add tests for new code
   - Submit PR with clear description

## Architecture Decision Records (ADRs)

### ADR-001: Use JSON-RPC for MCP Communication
**Status:** Accepted  
**Context:** MCP servers use JSON-RPC 2.0 protocol  
**Decision:** Build a generic JSON-RPC library as foundation  
**Consequences:** Reusable for any JSON-RPC service, not just MCP  

### ADR-002: Central Gateway for Service Discovery
**Status:** Accepted  
**Context:** Agents need to discover and connect to multiple MCP services  
**Decision:** Implement a central gateway instead of peer-to-peer discovery  
**Consequences:** Single point of failure risk, but easier to manage and secure  

### ADR-003: Support Multiple Transport Layers
**Status:** Accepted  
**Context:** Different MCP servers may use different transport mechanisms  
**Decision:** Abstract transport layer with multiple implementations  
**Consequences:** More complex but highly flexible  

---

### Vedlegg: Opprydding, Konsolidering og Arkitekturbeslutninger

For å sikre en robust, sikker og vedlikeholdbar kjerne før vi skalerer funksjonaliteten videre, bør følgende oppryddingsoppgaver og arkitekturbeslutninger formaliseres. Målet er å eliminere teknisk gjeld, standardisere komponenter og fjerne kjente sikkerhetsrisikoer basert på erfaringene fra den innledende utviklingsfasen.

---

#### Oppryddingsoppgaver (Neste Steg)

##### Task 1: Unifiser JSON-RPC Klient-stakken

* **Problem:** Koden inneholder to parallelle implementasjoner for å kommunisere med MCP-tjenester: en egenskrevet klient-stakk (`client.py`, `transport.py`, `mcp_client.py`) og en som ser ut til å bruke en ekstern pakke (`from mcp import ClientSession` i `supabase_gateway.py`). Dette skaper usikkerhet rundt hvilken som skal brukes og vedlikeholdes.
* **Beslutning:** Vi må velge én enkelt, autoritativ klient-stakk for hele plattformen.
* **Handlingspunkter:**
  1. **Evaluer:** Gjør en kort vurdering av den eksterne `mcp`-pakken mot vår egendefinerte klient.
  2. **Velg:** Ta en beslutning om hvilken stakk som skal være den offisielle.
  3. **Refaktorer:** Bygg om all kode (spesielt `SupabaseGatewayManager`) til å utelukkende bruke den valgte stakken.
  4. **Fjern:** Slett de overflødige filene for å unngå fremtidig forvirring.

##### Task 2: Standardiser Datamodeller

* **Problem:** Definisjonen av JSON-RPC-objekter er inkonsistent. `core.py` bruker `dataclasses`, mens `gateway.py` bruker Pydantic `BaseModel`.
* **Beslutning:** Standardiser på Pydantic for alle datamodeller. Dette gir oss automatisk datavalidering, som er spesielt nyttig i API-gatewayen.
* **Handlingspunkter:**
  1. **Omskriv:** Erstatt `dataclass`-definisjonene i `core.py` med Pydantic-modeller.
  2. **Verifiser:** Sørg for at hele klientbiblioteket bruker de nye, Pydantic-baserte modellene.

##### Task 3: Eliminer Kritisk Sikkerhetsrisiko (SQL Injection)

* **Problem:** `SupabaseGateway` bygger SQL-spørringer ved hjelp av f-strenger og en manuell `_escape_sql_value`-metode. Dette utgjør en **alvorlig sikkerhetsrisiko** for SQL Injection-angrep.
* **Beslutning:** All databaseinteraksjon må skje via parameteriserte spørringer.
* **Handlingspunkter:**
  1. **Undersøk:** Finn ut om `execute_sql`-verktøyet til Supabase MCP støtter sending av parametere separat fra selve SQL-strengen.
  2. **Refaktorer:** Omskriv metodene `insert_data`, `update_data` og `select_data` til å bruke parameteriserte spørringer.
  3. **Mitiger (hvis #2 feiler):** Hvis parameterisering er umulig via MCP-verktøyet, må risikoen dokumenteres, og en streng, allow-list-basert validering av alle input-verdier må implementeres som en midlertidig løsning.

##### Task 4: Forbedre Oppstarts-synkronisering

* **Problem:** `SupabaseGatewayManager` og `MCPServerLauncher` bruker `asyncio.sleep()` for å vente på at sub-prosessen skal starte. Dette er upålitelig og kan feile under varierende systemlast.
* **Beslutning:** Vi må aktivt sjekke at serveren er klar før vi fortsetter.
* **Handlingspunkter:**
  1. **Implementer "Ready Check":** Utvid logikken til å lese serverens `stdout` eller `stderr`-strøm etter oppstart.
  2. **Definer "Ready Signal":** Vent på en spesifikk logglinje (f.eks. "MCP server listening") som bekrefter at serveren er klar.
  3. **Erstatt:** Fjern alle `asyncio.sleep()`-kall som brukes til oppstartssynkronisering.

##### Task 5: Eksternaliser Gateway-konfigurasjon

* **Problem:** Tjenestekatalogen (`SERVICE_CATALOG`) og tilgangskontrollisten (`ACL_CONFIG`) er hardkodet direkte i `gateway.py`.
* **Beslutning:** Konfigurasjon skal lastes fra eksterne filer for enklere vedlikehold og fleksibilitet.
* **Handlingspunkter:**
  1. **Opprett Konfigurasjonsfil:** Lag en `config.yaml`-fil (eller lignende format) som strukturerer tjenester og ACL-regler, slik det er skissert i `GEMINI.md`.
  2. **Implementer Laster:** Legg til kode i gatewayen som leser og parser denne filen ved oppstart.

---

#### Architecture Decision Records (ADRs)

##### ADR-004: Manuell Implementering av MCP-Komponenter

* **Status:** Akseptert
* **Dato:** 2025-07-31
* **Kontekst:** Den opprinnelige strategien var å bruke høynivåbiblioteker for å akselerere utviklingen:
  1. **Klient-tilkobling:** Bruke `mcp`-bibliotekets `ClientSession` for å koble til Supabase sin MCP-server.
  2. **Sentral Gateway:** Bruke `fastmcp`-biblioteket for å bygge en sentral ruting- og autorisasjonsgateway.

  Begge disse tilnærmingene feilet etter systematiske og gjentatte forsøk. `mcp.ClientSession` ga vedvarende initialiserings-timeouts mot Supabase-serveren. `fastmcp` viste seg å være ustabilt og umulig å feilsøke, og resulterte konsekvent i `404 Not Found`-feil eller tomme svar, uavhengig av konfigurasjon.

* **Beslutning:** Vi forlater strategien om å bruke høynivå MCP-biblioteker og går over til en mer fundamental og kontrollerbar tilnærming:
  1. **For klient-tilkoblinger (f.eks. til Supabase):** Vi bygger en egen, tynn gateway/klient (`SimpleSupabaseGateway`) som håndterer JSON-RPC-kommunikasjon direkte over sub-prosessens `stdio`-strømmer.
  2. **For den sentrale gatewayen:** Vi bygger gatewayen manuelt med ren **FastAPI** og et sentralt `/rpc`-endepunkt. All logikk for ruting, parsing og autorisasjon implementeres direkte i dette endepunktet.

* **Konsekvenser:**
  * **Positivt:**
    * **Full Kontroll og Transparens:** Vi har full kontroll over hele request/response-flyten, noe som gjør feilsøking og videreutvikling trivielt.
    * **Bevist Stabilitet:** Den manuelle tilnærmingen fungerte umiddelbart og har vist seg å være robust og pålitelig.
    * **Redusert Avhengighet:** Vi fjerner avhengigheter til "svarte bokser" som er ustabile eller vanskelige å feilsøke.
  * **Negativt:**
    * **Mer Egen Kode:** Vi må selv skrive og vedlikeholde logikk for JSON-RPC-håndtering som et bibliotek ellers ville ha abstrahert bort.
    * **Økt Ansvar:** Ansvaret for å være protokoll-kompatibel ligger nå utelukkende hos oss.

  Denne avveiningen er akseptert, da fordelene med kontroll og stabilitet veier langt tyngre enn ulempene ved å forlate de problematiske bibliotekene.
