# GEMINI.md - Utviklingspartner for Anskaffelsesassistenten (v4.2)

### Role

Du er min partner som senior Python-utvikler og AI-arkitekt. Vi har nå fullført en grunnleggende, ende-til-ende MVP og går inn i neste fase av utviklingen.

Ditt fokus er å hjelpe meg å erstatte de enkle, regelbaserte komponentene med avansert funksjonalitet, spesielt ved å implementere en robust RAG-løsning for `OslomodellAgent`.

**Kjernekompetanse:**
* Python 3.x, Pydantic, async/await, Structlog
* Supabase (Postgres, RLS) og direkte JSON-RPC-integrasjon (Model Context Protocol)
* Google Gemini API med avansert RAG (hybrid søk)
* **Erfaring:** Vellykket implementering av LAO-mønsteret med direkte Python-kall for å unngå bibliotek-ustabilitet.

---
### Fullført Arbeid (Status: 31. juli 2025)

En betydelig MVP er fullført, som validerer kjerneflyten og arkitekturen.

* **✅ Stabil Database-integrasjon:** En egen, robust `SimpleSupabaseGateway` er utviklet og implementert. Den kommuniserer stabilt med Supabase sitt MCP-backend over `stdio` og eliminerer problemene som ble opplevd med eksterne `mcp`-biblioteker.
* **✅ Fullført Regelbasert Orkestreringsflyt:** `ProcurementOrchestrator` håndterer nå en komplett, ende-til-ende-prosess. Den kaller `TriageAgent`, den regelbaserte versjonen av `OslomodellAgent` og den mal-baserte `ProtocolGenerator` i korrekt sekvens. Dette beviser at LAO-arkitekturen med direkte metodekall mellom komponentene fungerer som forventet.
* **✅ Grunnleggende LAO-struktur på plass:** Prosjektet følger en klar mappestruktur som skiller mellom orkestratorer (N2), spesialister (N3) og verktøy (N4), i tråd med rammeverket.

---
### Neste Steg: Sprint 1 – Implementering av Avansert RAG

**Mål:** Erstatte den enkle, regelbaserte `OslomodellAgent` med en avansert versjon som henter kunnskap fra en egen database ved hjelp av hybrid RAG (Retrieval-Augmented Generation).

#### Task 1: Etablere RAG-Infrastruktur i Supabase

Denne oppgaven legger det tekniske fundamentet for kunnskapsbasen i databasen.

* **Opprette Tabellstruktur:** To nye tabeller må opprettes. `oslomodell_dokumenter` vil holde metadata om kildedokumentene (f.eks. navn, versjon, type). `oslomodell_chunks` vil inneholde de faktiske tekstbitene, deres tilhørende vektor-embedding og strukturert metadata (f.eks. tema, paragraf).
* **Etablere Indekser for Ytelse:** For at søk skal være raskt, må vi opprette spesialiserte indekser. En **GIN-indeks** på metadata-feltet vil sørge for lynrask filtrering (f.eks. hent kun chunks med `tema: "Miljøkrav"`). En **IVFFlat** eller **HNSW-indeks** på selve embedding-vektoren er kritisk for å effektivt kunne utføre likhetssøk blant tusenvis av tekstbiter.
* **Implementere Hybrid Søkefunksjon:** En lagret prosedyre i PostgreSQL (`hybrid_search`) skal lages. Denne funksjonens ansvar er å kombinere et semantisk vektorsøk med presis metadata-filtrering i én enkelt, atomisk operasjon. Dette gir oss det beste fra to verdener: å finne relevant innhold basert på betydning, samtidig som vi kan avgrense søket til spesifikke dokumenttyper eller temaer.

#### Task 2: Bygge og Kjøre Ingest-Verktøy

Målet med denne oppgaven er å populere kunnskapsbasen med innholdet fra Oslomodellen.

* **Utvikle `KnowledgeIngester`:** Et Python-skript skal utvikles for å lese data, for eksempel fra en forberedt CSV-fil.
* **Prosessere Hver Tekstbit:** For hver rad i CSV-filen skal skriptet utføre følgende:
  1. Hente ut tekstinnhold og relevant metadata (tema, paragraf, etc.).
  2. Kalle Gemini API for å generere en vektor-embedding for teksten. Det er kritisk at `task_type="RETRIEVAL_DOCUMENT"` spesifiseres her, slik at embeddingen optimaliseres for gjenfinning.
  3. Lagre den originale teksten, den genererte embeddingen og metadataen som en ny rad i `oslomodell_chunks`-tabellen via vår `SimpleSupabaseGateway`.

#### Task 3: Oppgradere `OslomodellAgent` til å bruke RAG

Dette er kjernen i sprinten, der vi bytter ut den enkle `if/else`-logikken med en intelligent, kunnskapsbasert prosess.

* **Implementere Tosteget Prosess:** Agentens nye logikk vil bestå av to hovedsteg:
  1. **Planlegging og Konteksthenting:** Først analyserer agenten den innkommende anskaffelsesforespørselen for å lage en "plan", som består av å identifisere relevante temaer (`Seriøsitetskrav`, `Miljøkrav`, etc.). Deretter genererer den en embedding av selve forespørselen (med `task_type="RETRIEVAL_QUERY"`) og kaller `hybrid_search`-funksjonen i databasen for å hente de mest relevante tekstbitene som matcher både semantikk og de identifiserte temaene.
  2. **Syntese og Vurdering:** Agenten mottar de relevante tekstutdragene fra databasen. Den kombinerer så denne rike, faktabaserte konteksten med den opprinnelige forespørselen, og sender alt til Gemini LLM for å generere en helhetlig og godt begrunnet vurdering.

#### Task 4: Implementere Nye Integrasjonstester

For å verifisere at den nye, komplekse logikken fungerer korrekt, må vi lage målrettede tester.

* **Verifisere Ende-til-Ende RAG-flyt:** Testene må bekrefte at `OslomodellAgent`, når den kalles av orkestratoren, faktisk utfører et søk mot databasen og at resultatet som returneres er basert på konteksten den henter derfra.
* **Teste for "Semantisk Kollisjon":** Vi må designe test-caser som sikrer at metadata-filtreringen fungerer. For eksempel, en forespørsel som primært handler om seriøsitetskrav skal ikke få forurenset kontekst fra tekstbiter som kun omhandler miljøkrav, selv om de semantisk kan være like.


### Kunnskapsbase Setup - Hybrid RAG Infrastructure

#### Steg 0: Datamodell for kunnskapsbase (Gjør dette først!)

**Kommando: /kunnskapsbase-setup**

**NB: Sjekk dokumentasjon før implementering av kode**: https://ai.google.dev/gemini-api/docs/embeddings

Opprett tabellstrukturen for hybrid RAG:

```sql
-- Metadata-tabell for dokumenter
CREATE TABLE oslomodell_dokumenter (
    dokument_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dokument_navn TEXT NOT NULL,
    dokument_type TEXT, -- 'instruks', 'forskrift', 'veileder'
    versjon TEXT,
    gyldig_fra DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```
```sql
-- Chunks med embeddings og metadata
CREATE TABLE oslomodell_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dokument_id UUID REFERENCES oslomodell_dokumenter(dokument_id),
    innhold TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb, -- tema, paragraf, nøkkelord
    embedding vector(768), -- Gemini text-embedding-004
    chunk_nummer INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```
```sql
-- Indekser for hybrid søk
CREATE INDEX idx_chunks_metadata ON oslomodell_chunks USING GIN (metadata);
CREATE INDEX idx_chunks_embedding ON oslomodell_chunks USING ivfflat (embedding vector_cosine_ops);

-- Funksjon for hybrid søk
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(768),
    metadata_filter JSONB DEFAULT '{}'::jsonb,
    match_count INT DEFAULT 5,
    similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    chunk_id UUID,
    innhold TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.chunk_id,
        c.innhold,
        c.metadata,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM oslomodell_chunks c
    WHERE 
        (metadata_filter = '{}'::jsonb OR c.metadata @> metadata_filter)
        AND 1 - (c.embedding <=> query_embedding) > similarity_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

#### Ingest-verktøy for kunnskapsbase

**Kommando: /ingest-tools**

Lag verktøy for å bygge kunnskapsbasen:

```python
# tools/knowledge_ingester.py
import pandas as pd
from typing import List, Dict, Optional
import asyncio
from pathlib import Path

class KnowledgeIngester:
    """Verktøy for å bygge hybrid RAG kunnskapsbase"""
    
    def __init__(self, supabase_gateway, gemini_gateway):
        self.db = supabase_gateway
        self.llm = gemini_gateway
        self.embedding_model = "models/text-embedding-004"
    
    async def ingest_from_csv(self, csv_path: str):
        """
        Ingest fra ferdig forberedt CSV med kolonner:
        - innhold: Teksten som skal indekseres
        - tema: Hovedkategori (Seriøsitetskrav, Miljøkrav, etc)
        - paragraf: Paragrafnummer
        - nøkkelord: Kommaseparerte nøkkelord
        """
        df = pd.read_csv(csv_path)
        
        # Opprett hoveddokument
        dokument_id = await self._create_document_record(
            navn=Path(csv_path).stem,
            type="instruks"
        )
        
        # Prosesser chunks
        for idx, row in df.iterrows():
            metadata = {
                "tema": row.get('tema', ''),
                "paragraf": row.get('paragraf', ''),
                "nøkkelord": row.get('nøkkelord', '').split(',')
            }
            
            # Generer embedding
            embedding = await self.llm.create_embedding(
                row['innhold'],
                task_type="RETRIEVAL_DOCUMENT"
            )
            
            # Lagre chunk
            await self._store_chunk(
                dokument_id=dokument_id,
                innhold=row['innhold'],
                metadata=metadata,
                embedding=embedding,
                chunk_nummer=idx
            )
            
            print(f"✅ Chunk {idx}: {row['innhold'][:50]}...")
    
    async def ingest_from_document(self, 
        file_path: str, 
        chunking_strategy: Optional[Dict] = None
    ):
        """
        Ingest fra PDF/Word med intelligent chunking
        """
        # Les dokument
        content = await self._read_document(file_path)
        
        # Default chunking-strategi for Oslomodell
        if not chunking_strategy:
            chunking_strategy = {
                "method": "semantic_sections",
                "section_markers": [
                    r"^\d+\.\s+",  # 1. Overskrift
                    r"^[a-z]\)\s+",  # a) Underpunkt
                    r"^§\s*\d+"  # § Paragraf
                ],
                "min_chunk_size": 200,
                "max_chunk_size": 1500
            }
        
        # Chunk dokumentet
        chunks = await self._chunk_document(content, chunking_strategy)
        
        # Ekstrahér metadata for hver chunk
        dokument_id = await self._create_document_record(
            navn=Path(file_path).stem,
            type="instruks"
        )
        
        for idx, chunk in enumerate(chunks):
            # La LLM ekstrahere metadata
            metadata = await self._extract_metadata(chunk)
            
            # Generer embedding
            embedding = await self.llm.create_embedding(
                chunk,
                task_type="RETRIEVAL_DOCUMENT"
            )
            
            # Lagre
            await self._store_chunk(
                dokument_id=dokument_id,
                innhold=chunk,
                metadata=metadata,
                embedding=embedding,
                chunk_nummer=idx
            )
    
    async def _extract_metadata(self, chunk: str) -> Dict:
        """La LLM ekstrahere strukturert metadata"""
        prompt = f"""
        Analyser denne teksten fra Oslomodellen og ekstraher metadata:
        
        Tekst: {chunk}
        
        Returner JSON med:
        - tema: Hovedkategori (Seriøsitetskrav/Miljøkrav/Lærlinger/IKT-krav/Aktsomhet)
        - paragraf: Eventuelt paragrafnummer
        - nøkkelord: Liste med relevante nøkkelord
        - gjelder_for: Typer anskaffelser dette gjelder for
        """
        
        response = await self.llm.generate_json(prompt)
        return response

#### Interaktiv ingest-guide

**Kommando: /guide-ingest**

Lag en interaktiv guide for brukeren:

```python
# tools/ingest_guide.py
class IngestGuide:
    """Interaktiv guide for kunnskapsbase-bygging"""
    
    async def start_interactive_session(self):
        print("🚀 Velkommen til kunnskapsbase-byggeren!")
        print("\nVelg ingest-metode:")
        print("1. CSV med ferdig strukturerte chunks")
        print("2. PDF/Word-dokument som skal chunkes")
        
        choice = input("\nDitt valg (1/2): ")
        
        if choice == "1":
            await self._csv_workflow()
        else:
            await self._document_workflow()
    
    async def _csv_workflow(self):
        print("\n📊 CSV-basert ingest")
        print("Forventet format:")
        print("- innhold: Teksten som skal indekseres")
        print("- tema: Seriøsitetskrav/Miljøkrav/etc")
        print("- paragraf: f.eks '4.1' eller '§7'")
        print("- nøkkelord: kommaseparerte")
        
        csv_path = input("\nSti til CSV-fil: ")
        
        # Forhåndsvisning
        df = pd.read_csv(csv_path)
        print(f"\nFant {len(df)} rader")
        print("\nForhåndsvisning:")
        print(df.head())
        
        confirm = input("\nFortsette? (j/n): ")
        if confirm.lower() == 'j':
            await ingester.ingest_from_csv(csv_path)
    
    async def _document_workflow(self):
        print("\n📄 Dokument-basert ingest")
        file_path = input("Sti til dokument: ")
        
        print("\nChunking-strategi:")
        print("1. Standard Oslomodell (anbefalt)")
        print("2. Paragraf-basert")
        print("3. Fast størrelse")
        
        strategy_choice = input("\nVelg strategi (1-3): ")
        
        # Vis eksempel på chunks
        preview_chunks = await self._preview_chunks(file_path, strategy_choice)
        print(f"\nForhåndsvisning av chunks:")
        for i, chunk in enumerate(preview_chunks[:3]):
            print(f"\n--- Chunk {i+1} ---")
            print(chunk[:200] + "...")
        
        confirm = input("\nFortsette? (j/n): ")
        if confirm.lower() == 'j':
            await ingester.ingest_from_document(file_path)
```

#### Testing av kunnskapsbase

**Kommando: /test-kunnskapsbase**

Verifiser at hybrid søk fungerer:

```python
# tests/test_knowledge_base.py
async def test_hybrid_search():
    """Test at hybrid søk returnerer relevante resultater"""
    
    # Test 1: Semantisk søk
    query = "Hvilke miljøkrav gjelder for byggeplasser?"
    results = await search_knowledge(
        query=query,
        metadata_filter={"tema": "Miljøkrav"}
    )
    assert len(results) > 0
    assert "fossilfri" in results[0]['innhold'].lower()
    
    # Test 2: Metadata-filtrering forhindrer kollisjon
    query = "krav til leverandører"
    seriøs_results = await search_knowledge(
        query=query,
        metadata_filter={"tema": "Seriøsitetskrav"}
    )
    aktsomhet_results = await search_knowledge(
        query=query,
        metadata_filter={"tema": "Aktsomhet"}
    )
    
    # Verifiser at resultatene er forskjellige
    assert seriøs_results[0]['chunk_id'] != aktsomhet_results[0]['chunk_id']
```

### Eksempel CSV-format for Oslomodell

**Kommando: /eksempel-csv**

```csv
innhold,tema,paragraf,nøkkelord
"Alle leverandører skal ha ordnede arbeidsforhold og etterleve grunnleggende menneskerettigheter. Dette inkluderer HMS-kort for alle arbeidere på byggeplass.",Seriøsitetskrav,4.1,"HMS-kort,arbeidsforhold,byggeplass"
"For anskaffelser over 500 000 kroner skal det gjennomføres en aktsomhetsvurdering for å identifisere risiko for brudd på grunnleggende menneskerettigheter.",Aktsomhet,7.1,"aktsomhetsvurdering,menneskerettigheter,terskelverdi"
"Alle bygge- og anleggsprosjekter skal benytte fossilfrie løsninger der det er mulig.",Miljøkrav,5.2,"fossilfri,byggeplass,miljø"
```

#### Steg 1: Datamodell-utvidelse (Uke 1)

**Kommando: /datamodell-setup**

Implementer gradvis de nye tabellene:

```sql
-- Fase 1: Kjernetabeller (start her)
CREATE TABLE anskaffelsesprosjekter (
    anskaffelses_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prosjektnavn TEXT NOT NULL,
    anskaffelsestype TEXT, -- 'vare', 'tjeneste', 'bygge-og-anlegg'
    estimert_verdi_eks_mva DECIMAL(12,2),
    triage_farge TEXT, -- 'GRØNN', 'GUL', 'RØD'
    gjeldende_status TEXT DEFAULT 'Opprettet',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS og indekser
ALTER TABLE anskaffelsesprosjekter ENABLE ROW LEVEL SECURITY;
CREATE INDEX idx_anskaffelser_status ON anskaffelsesprosjekter(gjeldende_status);
CREATE INDEX idx_anskaffelser_triage ON anskaffelsesprosjekter(triage_farge);

**Python-integrasjon:**

```python
# Utvid SimpleSupabaseGateway gradvis
async def opprett_anskaffelse(self, request: AnskaffelseRequest) -> str:
    """Oppretter hovedprosjekt med minimal data først"""
    # Start enkelt, utvid gradvis
```

#### Steg 2: Oslomodell-agent med Hybrid RAG (Uke 1-2)

**Kommando: /oslomodell-hybrid**

Implementer Oslomodell-agenten basert på erfaringene fra prosjektloggen:

```python
# specialists/oslomodell_agent.py
class OslomodellAgent:
    """N3 Spesialist med hybrid RAG for Oslomodell-vurdering"""
    
    def __init__(self, gemini_gateway: GeminiGateway, supabase_gateway: SimpleSupabaseGateway):
        self.llm = gemini_gateway
        self.db = supabase_gateway
        # Hardkodede terskelverdier (fjerner behov for eksterne verktøy)
        self.lærling_terskel = 1_750_000
        self.aktsomhet_terskel = 500_000
    
    async def vurder_krav(self, request: AnskaffelseRequest) -> OslomodellVurdering:
        # 1. Intelligent planlegging (mindre skripting)
        plan = await self._lag_plan(request)
        
        # 2. Hybrid søk med metadata-filtrering
        kontekst = await self._hent_relevant_kontekst(plan, request)
        
        # 3. Syntese med regelsjekk
        return await self._generer_vurdering(request, kontekst)
    
    async def _lag_plan(self, request: AnskaffelseRequest) -> List[str]:
        """La LLM planlegge selv med minimal skripting"""
        prompt = f"""
        Analyser denne anskaffelsen og identifiser relevante Oslomodell-temaer:
        - Type: {request.anskaffelsestype}
        - Verdi: {request.estimert_verdi} NOK
        - Beskrivelse: {request.beskrivelse}
        
        Mulige temaer: Seriøsitetskrav, Miljøkrav, Lærlinger, IKT-krav
        Returner kun relevante temaer som JSON: {{"temaer": [...]}}
        """
        
        response = await self.llm.generate_json(prompt)
        return response.get("temaer", [])
```

**Hybrid RAG-implementering:**

```python
async def _hent_relevant_kontekst(self, temaer: List[str], request: AnskaffelseRequest) -> str:
    """Hybrid søk: embedding + metadata-filtrering"""
    
    kontekst = ""
    query_embedding = await self.llm.create_embedding(str(request))
    
    for tema in temaer:
        # MCP-kall via Supabase for hybrid søk
        results = await self.db.execute_sql(
            """
            SELECT content, metadata
            FROM oslomodell_dokumenter
            WHERE metadata->>'tema' = $1
            ORDER BY embedding <-> $2
            LIMIT 3
            """,
            [tema, query_embedding]
        )
        
        kontekst += f"\n--- {tema} ---\n"
        kontekst += "\n".join([r['content'] for r in results])
    
    return kontekst
```

#### Steg 3: Forenklet verktøy-simulering (Uke 2)

**Kommando: /simuler-verktoy**

Simuler MCP-verktøy internt i stedet for eksterne kall:

```python
# specialists/oslomodell_agent.py
class OslomodellAgent:
    async def _sjekk_lærlingkrav(self, request: AnskaffelseRequest) -> bool:
        """Simulert verktøy - hardkodet logikk"""
        if request.anskaffelsestype == "bygge-og-anlegg":
            if request.estimert_verdi >= self.lærling_terskel:
                if request.varighet_måneder > 3:
                    return True
        return False
    
    async def _sjekk_aktsomhet(self, request: AnskaffelseRequest) -> bool:
        """Enkel regelsjekk - ingen eksterne kall"""
        return request.estimert_verdi >= self.aktsomhet_terskel
```

#### Steg 4: ProtocolGenerator (Uke 2-3)

**Kommando: /protocol-generator**

```python
# specialists/protocol_generator.py
class ProtocolGenerator:
    """N3 Spesialist for protokollgenerering"""
    
    async def generer(
        self, 
        request: AnskaffelseRequest,
        triage: TriageResult,
        oslomodell: OslomodellVurdering
    ) -> Protokoll:
        # Bruk Gemini til å generere basert på mal
        # Integrer Oslomodell-krav i protokollen
```

#### Steg 5: Oppdatert Orkestrator (Uke 3)

**Kommando: /oppdater-orkestrator**

```python
class ProcurementOrchestrator:
    async def process_request(self, request: AnskaffelseRequest) -> ProcurementResult:
        # 1. Opprett i ny datamodell
        anskaffelses_id = await self.db.opprett_anskaffelse(request)
        
        # 2. Triage
        triage = await self.triage_agent.vurder(request)
        await self.db.oppdater_triage(anskaffelses_id, triage)
        
        # 3. Oslomodell-vurdering (for alle, ikke bare GUL/RØD)
        oslomodell = await self.oslomodell_agent.vurder_krav(request)
        
        # 4. Protokoll for GRØNN
        if triage.color == TriageColor.GRØNN:
            protokoll = await self.protocol_generator.generer(
                request, triage, oslomodell
            )
        
        # 5. Lagre alt i ny struktur
        await self._lagre_komplett_resultat(
            anskaffelses_id, triage, oslomodell, protokoll
        )
```

### Hybrid RAG Best Practices

Fra din tidligere suksess:

1. **Planlegging er kritisk** - Men la LLM gjøre mer av jobben
2. **Metadata-filtrering forhindrer semantisk kollisjon**
3. **Kombiner intern kontekst med hardkodede regler**
4. **Unngå for granulær chunking** - Hele seksjoner fungerer bedre

**Chunking-strategi for Oslomodellen:**

```python
# Ved ingest av Oslomodell-dokumenter
chunking_strategy = {
    "method": "section_based",  # Ikke atomisk punkt-splitting
    "metadata_extraction": {
        "tema": "regex_pattern",  # Seriøsitetskrav, Miljøkrav, etc.
        "paragraf": "nummer"
    }
}
```

-----

### Testing Strategy

**Kommando: /test-oslomodell**

Generer testcases som dekker:

- Grensetilfeller (verdi på eksakt 500k, 1.75M)
- Ulike anskaffelsestyper
- Kombinasjoner av krav
- Edge cases fra prosjektloggen

```python
# tests/test_oslomodell_hybrid.py
@pytest.mark.asyncio
async def test_hybrid_rag_no_semantic_collision():
    """Verifiser at seriøsitetskrav og aktsomhet ikke blandes"""
    # Test case fra prosjektloggen
```

-----

### Common Commands Summary

- `/datamodell-setup` - SQL og migreringsscript
- `/oslomodell-hybrid` - Implementer hybrid RAG
- `/simuler-verktoy` - Interne verktøy-simuleringer
- `/protocol-generator` - Mal-basert generering
- `/oppdater-orkestrator` - Full flyt-integrasjon
- `/test-oslomodell` - Spesifikke test-cases
- `/chunk-strategi` - Optimal chunking for Oslomodell
