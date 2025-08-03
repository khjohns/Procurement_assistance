# GEMINI.md - Implementering av RPC Gateway i Anskaffelsesassistenten

## Oversikt

Dette dokumentet beskriver hvordan du implementerer den nye RPC Gateway-arkitekturen i Anskaffelsesassistenten. Gatewayen erstatter `SimpleSupabaseGateway` med en mer robust, skalerbar og sikker løsning basert på PostgreSQL RPC-funksjoner.

## Arkitektonisk sammenheng

### Nåværende arkitektur

```
ProcurementOrchestrator (Nivå 2)
    ├── TriageAgent (Spesialist)
    │   └── GeminiGateway (Verktøy)
    ├── ProtocolGenerator (Spesialist)
    │   └── GeminiGateway (Verktøy)
    └── SimpleSupabaseGateway (Verktøy) ← Skal erstattes
```

### Ny arkitektur

```
ProcurementOrchestrator (Nivå 2)
    ├── TriageAgent (Spesialist)
    │   └── GeminiGateway (Verktøy)
    ├── ProtocolGenerator (Spesialist)
    │   └── GeminiGateway (Verktøy)
    └── RPCGatewayClient (Verktøy) → RPC Gateway Server → PostgreSQL
```

## Implementeringssteg

### Steg 1: Database-oppsett

#### 1.1 Opprett RPC-funksjoner i Supabase

```sql
-- Funksjon for å lagre triageresultat
CREATE OR REPLACE FUNCTION lagre_triage_resultat(
    p_request_id TEXT,
    p_farge TEXT,
    p_begrunnelse TEXT,
    p_confidence FLOAT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_resultat_id UUID;
BEGIN
    -- Validering
    IF p_farge NOT IN ('GRØNN', 'GUL', 'RØD') THEN
        RAISE EXCEPTION 'Ugyldig farge: %', p_farge;
    END IF;
    
    IF p_confidence < 0 OR p_confidence > 1 THEN
        RAISE EXCEPTION 'Confidence må være mellom 0 og 1: %', p_confidence;
    END IF;
    
    -- Opprett eller oppdater triageresultat
    INSERT INTO triage_results (
        request_id,
        farge,
        begrunnelse,
        confidence,
        created_at,
        updated_at
    ) VALUES (
        p_request_id::UUID,
        p_farge,
        p_begrunnelse,
        p_confidence,
        NOW(),
        NOW()
    )
    ON CONFLICT (request_id) DO UPDATE SET
        farge = EXCLUDED.farge,
        begrunnelse = EXCLUDED.begrunnelse,
        confidence = EXCLUDED.confidence,
        updated_at = NOW()
    RETURNING id INTO v_resultat_id;
    
    -- Returner bekreftelse
    RETURN jsonb_build_object(
        'status', 'success',
        'resultat_id', v_resultat_id,
        'request_id', p_request_id,
        'melding', format('Triageresultat lagret for %s', p_farge)
    );
END;
$$;

-- Funksjon for å sette status
CREATE OR REPLACE FUNCTION sett_status(
    p_request_id TEXT,
    p_status TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Validering av status
    IF p_status NOT IN ('PENDING', 'TRIAGE_COMPLETE', 'PAUSED_FOR_REVIEW', 'PROTOCOL_GENERATED', 'COMPLETED') THEN
        RAISE EXCEPTION 'Ugyldig status: %', p_status;
    END IF;
    
    -- Oppdater status
    UPDATE procurement_requests
    SET 
        status = p_status,
        updated_at = NOW()
    WHERE id = p_request_id::UUID;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Request ikke funnet: %', p_request_id;
    END IF;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'request_id', p_request_id,
        'new_status', p_status,
        'timestamp', NOW()
    );
END;
$$;

-- Funksjon for å søke i Oslomodell-krav
CREATE OR REPLACE FUNCTION sok_oslomodell_krav(
    p_sokevektor vector(1536),
    p_kategori TEXT DEFAULT NULL,
    p_maks_resultater INTEGER DEFAULT 5,
    p_min_likhet FLOAT DEFAULT 0.7
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_resultater JSONB;
BEGIN
    -- Utfør hybrid søk
    SELECT jsonb_agg(
        jsonb_build_object(
            'chunk_id', c.id,
            'innhold', c.content,
            'likhetsscore', 1 - (c.embedding <=> p_sokevektor),
            'metadata', c.metadata,
            'kategori', c.metadata->>'kategori',
            'kilde', c.metadata->>'kilde'
        ) ORDER BY c.embedding <=> p_sokevektor
    ) INTO v_resultater
    FROM knowledge_chunks c
    WHERE 
        -- Vektorlikhet over terskel
        1 - (c.embedding <=> p_sokevektor) >= p_min_likhet
        -- Metadata-filter hvis spesifisert
        AND (p_kategori IS NULL OR c.metadata->>'kategori' = p_kategori)
        -- Kun Oslomodell-dokumenter
        AND c.metadata->>'dokument_type' = 'oslomodell'
    LIMIT p_maks_resultater;
    
    -- Returner resultater med metadata
    RETURN jsonb_build_object(
        'status', 'success',
        'antall_treff', jsonb_array_length(COALESCE(v_resultater, '[]'::jsonb)),
        'resultater', COALESCE(v_resultater, '[]'::jsonb),
        'sokekriterier', jsonb_build_object(
            'kategori', p_kategori,
            'min_likhet', p_min_likhet,
            'maks_resultater', p_maks_resultater
        )
    );
END;
$$;

-- Funksjon for å lagre protokoll
CREATE OR REPLACE FUNCTION lagre_protokoll(
    p_request_id TEXT,
    p_protokoll_tekst TEXT,
    p_confidence FLOAT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_protokoll_id UUID;
BEGIN
    INSERT INTO procurement_protocols (
        request_id,
        protocol_text,
        confidence,
        created_at
    ) VALUES (
        p_request_id::UUID,
        p_protokoll_tekst,
        p_confidence,
        NOW()
    ) RETURNING id INTO v_protokoll_id;
    
    -- Oppdater status på request
    UPDATE procurement_requests
    SET status = 'PROTOCOL_GENERATED', updated_at = NOW()
    WHERE id = p_request_id::UUID;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'protokoll_id', v_protokoll_id,
        'request_id', p_request_id
    );
END;
$$;

-- Sett opp nødvendige tabeller hvis de ikke eksisterer
CREATE TABLE IF NOT EXISTS procurement_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    navn TEXT NOT NULL,
    verdi INTEGER NOT NULL,
    beskrivelse TEXT,
    status TEXT DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS triage_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID UNIQUE REFERENCES procurement_requests(id),
    farge TEXT NOT NULL CHECK (farge IN ('GRØNN', 'GUL', 'RØD')),
    begrunnelse TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS procurement_protocols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES procurement_requests(id),
    protocol_text TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indekser for bedre ytelse
CREATE INDEX idx_triage_results_request_id ON triage_results(request_id);
CREATE INDEX idx_procurement_requests_status ON procurement_requests(status);
CREATE INDEX idx_knowledge_chunks_metadata ON knowledge_chunks USING GIN(metadata);
```

### Steg 2: Deploy RPC Gateway Server

#### 2.1 Opprett gateway-mappen

```bash
mkdir gateway
cd gateway
```

#### 2.2 Opprett requirements.txt

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
asyncpg==0.29.0
python-dotenv==1.0.0
structlog==23.2.0
pydantic==2.5.0
httpx==0.25.2  # For klient
```

#### 2.3 Kopier gateway-koden

Kopier den komplette `gateway_v2_complete.py` fra tidligere svar til `gateway/main.py`.

#### 2.4 Opprett .env fil for gateway

```env
DATABASE_URL=postgresql://[user]:[password]@[host]:[port]/[database]?sslmode=require
ADMIN_TOKEN=your-secure-admin-token
```

#### 2.5 Start gateway-serveren

```bash
cd gateway
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### 2.6 Viktig: pgbouncer konfigurasjon

Supabase bruker pgbouncer for connection pooling, som ikke støtter prepared statements. Gateway-koden håndterer dette automatisk ved å sette `statement_cache_size=0`. Dette er kritisk for at gateway skal fungere korrekt.

**Merk:** Hvis du får feil som "prepared statement already exists", sjekk at `statement_cache_size=0` er satt i både pool-opprettelsen og i RPC-funksjonen.


### Steg 3: Implementer RPC Gateway Client

#### 3.1 Opprett `tools/rpc_gateway_client.py`

```python
# tools/rpc_gateway_client.py
import httpx
import structlog
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()

class RPCError(Exception):
    """Custom exception for RPC errors"""
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"RPC Error {code}: {message}")

class RPCGatewayClient:
    """Client for communicating with the RPC Gateway"""
    
    def __init__(self, base_url: str = None, agent_id: str = "anskaffelsesassistenten"):
        self.base_url = base_url or os.getenv("RPC_GATEWAY_URL", "http://localhost:8000")
        self.agent_id = agent_id
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-Agent-ID": self.agent_id},
            timeout=30.0
        )
        self._request_id = 0
        logger.info("RPCGatewayClient initialized", 
                   base_url=self.base_url, 
                   agent_id=self.agent_id)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.client.__aenter__()
        # Test connection
        try:
            health = await self.client.get("/health")
            health_data = health.json()
            if health_data.get("database") != "healthy":
                logger.warning("Gateway database not healthy", health=health_data)
        except Exception as e:
            logger.error("Failed to check gateway health", error=str(e))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make an RPC call to the gateway"""
        self._request_id += 1
        
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._request_id
        }
        
        logger.info("Making RPC call", 
                   method=method, 
                   request_id=self._request_id,
                   params_keys=list(params.keys()) if params else [])
        
        try:
            response = await self.client.post("/rpc", json=request_data)
            response.raise_for_status()
            
            result = response.json()
            
            if "error" in result:
                error = result["error"]
                raise RPCError(
                    code=error.get("code", -1),
                    message=error.get("message", "Unknown error"),
                    data=error.get("data")
                )
            
            logger.info("RPC call successful", 
                       method=method,
                       request_id=self._request_id)
            
            return result.get("result")
            
        except httpx.HTTPError as e:
            logger.error("HTTP error during RPC call", 
                        method=method,
                        error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during RPC call",
                        method=method,
                        error=str(e),
                        exc_info=True)
            raise
    
    # Convenience methods for specific operations
    async def lagre_triage_resultat(self, request_id: str, triage_result) -> Dict[str, Any]:
        """Lagre triageresultat"""
        params = {
            "request_id": request_id,
            "farge": triage_result.farge,
            "begrunnelse": triage_result.begrunnelse,
            "confidence": triage_result.confidence
        }
        return await self.call("database.lagre_triage_resultat", params)
    
    async def sett_status(self, request_id: str, status: str) -> Dict[str, Any]:
        """Sett status på request"""
        params = {
            "request_id": request_id,
            "status": status
        }
        return await self.call("database.sett_status", params)
    
    async def sok_oslomodell_krav(self, sokevektor: list, kategori: str = None, 
                                  maks_resultater: int = 5) -> Dict[str, Any]:
        """Søk i Oslomodell-krav"""
        params = {
            "sokevektor": sokevektor,
            "maks_resultater": maks_resultater
        }
        if kategori:
            params["kategori"] = kategori
        
        return await self.call("database.sok_oslomodell_krav", params)
    
    async def lagre_protokoll(self, request_id: str, protokoll_tekst: str, 
                             confidence: float) -> Dict[str, Any]:
        """Lagre protokoll"""
        params = {
            "request_id": request_id,
            "protokoll_tekst": protokoll_tekst,
            "confidence": confidence
        }
        return await self.call("database.lagre_protokoll", params)
```

### Steg 4: Oppdater Orchestrator

#### 4.1 Erstatt SimpleSupabaseGateway med RPCGatewayClient

```python
# orchestrators/procurement_orchestrator.py
import structlog
from models.procurement_models import AnskaffelseRequest
from specialists.triage_agent import TriageAgent
from specialists.protocol_generator import ProtocolGenerator
from tools.rpc_gateway_client import RPCGatewayClient  # Ny import

logger = structlog.get_logger()

class ProcurementOrchestrator:
    def __init__(self, triage_agent: TriageAgent, protocol_generator: ProtocolGenerator):
        self.triage_agent = triage_agent
        self.protocol_generator = protocol_generator
        # RPCGatewayClient opprettes i kjor_prosess for bedre ressurshåndtering
        logger.info("ProcurementOrchestrator initialized", 
                    triage_agent=self.triage_agent, 
                    protocol_generator=self.protocol_generator)

    async def kjor_prosess(self, request: AnskaffelseRequest):
        async with RPCGatewayClient() as gateway:
            logger.info("Starting procurement process for request", request_id=request.id)
            
            try:
                # Steg 0: Opprett request i database (ny funksjonalitet)
                # Her kan du legge til en RPC-funksjon for å lagre selve requesten først
                
                # Steg 1: Kjør triagering
                triage_result = await self.triage_agent.vurder_anskaffelse(request)
                logger.info("Triage completed", request_id=request.id, result=triage_result)

                # Steg 2: Lagre triageringsresultat via RPC
                lagre_response = await gateway.lagre_triage_resultat(request.id, triage_result)
                logger.info("Triage result saved to database", 
                           request_id=request.id,
                           response=lagre_response)

                # Steg 3: Vurder neste steg basert på triage og konfidens
                pause_for_review = False
                if triage_result.farge == "RØD":
                    logger.warning("Triage result is RED, flagging for manual review.", 
                                 request_id=request.id)
                    pause_for_review = True
                elif triage_result.confidence < 0.85:
                    logger.warning("Confidence score is below threshold (0.85), flagging for manual review.", 
                                   request_id=request.id, 
                                   confidence=triage_result.confidence)
                    pause_for_review = True

                if pause_for_review:
                    status_response = await gateway.sett_status(request.id, "PAUSED_FOR_REVIEW")
                    logger.info("Process halted for manual review.", 
                               request_id=request.id,
                               status_response=status_response)
                    return triage_result

                # Hvis vi kommer hit, er det GRØNN/GUL med høy nok konfidens
                logger.info("Triage result is GREEN or YELLOW with high confidence, proceeding to protocol generation.", 
                            request_id=request.id, 
                            farge=triage_result.farge)
                
                # Steg 4: Generer protokoll
                protocol_result = await self.protocol_generator.generate_protocol(request)
                logger.info("Protocol generated", 
                            request_id=request.id, 
                            confidence=protocol_result.confidence)
                
                # Steg 5: Lagre protokoll via RPC
                protokoll_response = await gateway.lagre_protokoll(
                    request.id,
                    protocol_result.protocol_text,
                    protocol_result.confidence
                )
                logger.info("Protocol saved to database",
                           request_id=request.id,
                           response=protokoll_response)
                
                # Steg 6: Oppdater status
                await gateway.sett_status(request.id, "PROTOCOL_GENERATED")

                return protocol_result
                
            except Exception as e:
                logger.error("Error in procurement process",
                           request_id=request.id,
                           error=str(e),
                           exc_info=True)
                # Prøv å sette error status
                try:
                    await gateway.sett_status(request.id, "ERROR")
                except:
                    pass
                raise
```

### Steg 5: Implementer Oslomodell-søk i spesialistagenter

#### 5.1 Oppdater OslomodellAgent (hvis du har en)

```python
# specialists/oslomodell_agent.py
import structlog
from tools.rpc_gateway_client import RPCGatewayClient
from tools.embedding_gateway import EmbeddingGateway

logger = structlog.get_logger()

class OslomodellAgent:
    """Spesialistagent for Oslomodell-vurderinger"""
    
    def __init__(self, embedding_gateway: EmbeddingGateway):
        self.embedding_gateway = embedding_gateway
        logger.info("OslomodellAgent initialized")
    
    async def vurder_mot_oslomodell(self, beskrivelse: str, kategori: str = None):
        """Vurderer en beskrivelse mot relevante Oslomodell-krav"""
        
        # Generer embedding for søket
        sokevektor = await self.embedding_gateway.create_embedding(beskrivelse)
        
        async with RPCGatewayClient() as gateway:
            # Søk etter relevante krav
            sok_resultat = await gateway.sok_oslomodell_krav(
                sokevektor=sokevektor,
                kategori=kategori,
                maks_resultater=5
            )
            
            logger.info("Oslomodell search completed",
                       antall_treff=sok_resultat.get('antall_treff', 0))
            
            # Analyser resultater
            relevante_krav = []
            for resultat in sok_resultat.get('resultater', []):
                if resultat['likhetsscore'] > 0.8:  # Høy relevans
                    relevante_krav.append({
                        'krav': resultat['innhold'],
                        'kategori': resultat.get('kategori', 'Ukjent'),
                        'relevans': resultat['likhetsscore']
                    })
            
            return {
                'relevante_krav': relevante_krav,
                'antall_krav': len(relevante_krav),
                'har_kritiske_krav': any(k['kategori'] == 'Kritisk' for k in relevante_krav)
            }
```

### Steg 6: Miljøvariabler og konfigurasjon

#### 6.1 Oppdater .env

```env
# Eksisterende
GEMINI_API_KEY=your-gemini-key
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key

# Nye for RPC Gateway
RPC_GATEWAY_URL=http://localhost:8000
RPC_AGENT_ID=anskaffelsesassistenten
```

### Steg 7: Testing

#### 7.1 Test gateway direkte

```python
# test_gateway.py
import asyncio
import httpx
import json

async def test_gateway():
    async with httpx.AsyncClient() as client:
        # Test health
        health = await client.get("http://localhost:8000/health")
        print("Health:", health.json())
        
        # Test RPC call
        rpc_request = {
            "jsonrpc": "2.0",
            "method": "database.sett_status",
            "params": {
                "request_id": "test-123",
                "status": "PENDING"
            },
            "id": 1
        }
        
        response = await client.post(
            "http://localhost:8000/rpc",
            json=rpc_request,
            headers={"X-Agent-ID": "anskaffelsesassistenten"}
        )
        print("RPC Response:", response.json())

if __name__ == "__main__":
    asyncio.run(test_gateway())
```

#### 7.2 Test med orchestrator

```python
# test_orchestrator_with_gateway.py
import asyncio
from tools.rpc_gateway_client import RPCGatewayClient
import uuid  # Legg til denne

async def test_client():
    async with RPCGatewayClient() as client:
        # Bruk en gyldig UUID for testing
        test_request_id = str(uuid.uuid4())
        
        # Test status update
        result = await client.sett_status(test_request_id, "PENDING")
        print("Status result:", result)
        
        # Test triage save
        from models.procurement_models import TriageResult
        triage = TriageResult(
            farge="GRØNN",
            begrunnelse="Test begrunnelse",
            confidence=0.95
        )
        
        result = await client.lagre_triage_resultat(test_request_id, triage)
        print("Triage result:", result)

if __name__ == "__main__":
    asyncio.run(test_client())
```

### Steg 8: Overvåkning og vedlikehold

#### 8.1 Logg-aggregering

Gateway-serveren produserer strukturerte logger. Sett opp log-aggregering for å spore:

- Request rates per agent
- Feilrater per metode
- Responstider
- Database-helse

#### 8.2 Metrics dashboard

Bruk `/metrics` endepunktet til å lage et dashboard som viser:

- Antall requests per agent siste minutt
- Tilgjengelige tjenester
- Rate limit status

#### 8.3 Konfigurasjonsstyring

Bruk `/reload-config` endepunktet (med admin token) for å oppdatere ACL og tjenestekatalog uten restart.

## Migreringsstrategi

### Fase 1: Parallell kjøring

1. Deploy gateway uten å fjerne SimpleSupabaseGateway
2. Implementer RPCGatewayClient
3. Test grundig i dev/test miljø

### Fase 2: Gradvis overgang

1. Oppdater orchestrator til å bruke RPCGatewayClient for nye operasjoner
2. Behold SimpleSupabaseGateway for eksisterende funksjonalitet
3. Migrer én operasjon om gangen

### Fase 3: Full migrering

1. Erstatt all bruk av SimpleSupabaseGateway
2. Fjern SimpleSupabaseGateway fra kodebasen
3. Optimaliser RPC-funksjoner basert på faktisk bruk

## Beste praksis

### 1. Feilhåndtering

- Alltid wrap gateway-kall i try/except
- Logg både request og response
- Ha fallback-strategier for kritiske operasjoner

### 2. Ytelse

- Bruk connection pooling (allerede implementert)
- Vurder caching for hyppige, identiske søk
- Monitor responstider og optimaliser RPC-funksjoner

### 3. Sikkerhet

- Roter ADMIN_TOKEN regelmessig
- Bruk sterke, unike agent-IDer
- Implementer IP-whitelisting for produksjon
- Vurder TLS for gateway-kommunikasjon

### 4. Utvidbarhet

- Design RPC-funksjoner for gjenbruk
- Dokumenter input/output formater
- Versjonér API-endringer forsiktig

## Feilsøking


### pgbouncer / prepared statement feil

Symptom: `DuplicatePreparedStatementError: prepared statement "__asyncpg_stmt_1__" already exists`

Løsning:
- Sjekk at `statement_cache_size=0` er satt i pool-opprettelsen
- Verifiser at du bruker pooler URL (port 6543), ikke direct (port 5432)
- Hvis problemet vedvarer, restart gateway-serveren

Dette er en kjent begrensning med pgbouncer og asyncpg, og løses ved å disable statement caching.

### Gateway starter ikke

- Sjekk DATABASE_URL i .env
- Verifiser at PostgreSQL er tilgjengelig
- Se etter port-konflikter (8000)

### RPC-kall feiler

- Sjekk agent-ID i header
- Verifiser at metoden er i ACL
- Se gateway-logger for detaljer

### Database-feil

- Sjekk at RPC-funksjoner er opprettet
- Verifiser SECURITY DEFINER rettigheter
- Test funksjoner direkte i Supabase SQL Editor

## Konklusjon

Denne implementeringen gir deg:

- ✅ Eliminert SQL injection risiko
- ✅ Sentralisert tilgangskontroll
- ✅ Bedre observabilitet
- ✅ Enklere skalering
- ✅ Konsistent feilhåndtering

Følg stegene i rekkefølge og test grundig mellom hver fase. Gateway-arkitekturen vil gjøre systemet mer robust og enklere å vedlikeholde etter hvert som det vokser.​​​​​​​​​​​​​​​​