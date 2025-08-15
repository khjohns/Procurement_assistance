# chunk_agent.py -

import pandas as pd
import json
import uuid
import os
from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field, ValidationError
from enum import Enum

# ==============================================================================
# 1. DEFINISJON AV Pydantic-MODELLEN (CompleteChunkMetadata)
# ==============================================================================
# Dette er "malen" som LLM-en skal fylle ut for hver tekst-chunk.

class DocumentType(str, Enum):
    INSTRUKS = "instruks"
    BYRADSSAK = "byrådssak"
    KONTRAKTSMAL = "kontraktsmal"
    VEILEDER = "veileder"
    RAPPORT = "rapport"
    ANNET = "annet"

class ChunkLevel(str, Enum):
    DOCUMENT = "dokument"
    SECTION = "seksjon"
    SUBSECTION = "underseksjon"
    RULE = "regel"
    EXAMPLE = "eksempel"
    DEFINITION = "definisjon"

class RiskType(str, Enum):
    ARBEIDSLIVSKRIMINALITET = "arbeidslivskriminalitet"
    SOSIAL_DUMPING = "sosial_dumping"
    MILJO = "miljø"
    KORRUPSJON = "korrupsjon"
    MENNESKERETTIGHETER = "menneskerettigheter"
    INGEN = "ingen"

class Actor(str, Enum):
    UKE = "Utviklings- og kompetanseetaten"
    LEVERANDOR = "Leverandør"
    OPPDRAGSGIVER = "Oppdragsgiver"
    BYRADET = "Byrådet"
    VIRKSOMHET = "Virksomhet"
    BYM = "Bymiljøetaten"

class RuleStatus(str, Enum):
    ACTIVE = "aktiv"
    PROPOSED = "foreslått"
    EXPIRED = "utløpt"
    SUPERSEDED = "erstattet"

class CompleteChunkMetadata(BaseModel):
    chunk_id: str = Field(..., description="Unik ID for chunk (f.eks. UUID).")
    document_type: DocumentType = Field(..., description="Type kildedokument.")
    source_document_name: str = Field(..., description="Offisielt navn eller filnavn på kildedokumentet.")
    source_page: Optional[int] = Field(None, description="Sidetall i kildedokumentet.")
    source_paragraph: Optional[int] = Field(None, description="Avsnittsnummer på siden for nøyaktig sporing.")
    status: RuleStatus = Field(RuleStatus.ACTIVE, description="Status for regelen i denne chunk-en.")
    version: str = Field("1.0", description="Versjon av denne chunk-ens innhold/metadata.")
    chunk_level: ChunkLevel = Field(..., description="Hierarkisk nivå for denne chunk-en.")
    section_number: Optional[str] = Field(None, description="Seksjonsnummer fra kildedokumentet (f.eks. '4.2').")
    title: str = Field(..., description="Beskrivende tittel for chunk-en/seksjonen.")
    content_text: str = Field(..., description="Den nøyaktige teksten til chunk-en.")
    summary: str = Field(..., description="En kort, LLM-generert oppsummering (1-2 setninger).")
    actors: List[Actor] = Field(default_factory=list, description="Hvilke aktører/roller som er relevante.")
    risk_context: List[RiskType] = Field(default_factory=list, description="Hvilke typer risiko som omtales.")
    semantic_tags: List[str] = Field(default_factory=list, description="Frie semantiske tagger for forbedret søk.")
    keywords: List[str] = Field(default_factory=list, description="Viktige nøkkelord og synonymer fra teksten.")
    key_dates_and_deadlines: Dict[str, str] = Field(default_factory=dict, description="Strukturert oversikt over datoer.")
    key_values_and_thresholds: Dict[str, Any] = Field(default_factory=dict, description="Strukturert oversikt over verdier.")
    requirement_codes: List[str] = Field(default_factory=list, description="Liste over spesifikke kravkoder som nevnes.")
    applies_to_categories: List[str] = Field(default_factory=list, description="Hvilke anskaffelseskategorier regelen gjelder for.")
    conditions: List[Dict[str, Any]] = Field(default_factory=list, description="En strukturert liste over betingelser.")
    exceptions: List[str] = Field(default_factory=list, description="En liste med beskrivelser av unntak fra regelen.")
    parent_chunk_id: Optional[str] = Field(None, description="ID til overordnet chunk.")
    references_to_other_docs: List[str] = Field(default_factory=list, description="Referanser til andre dokumenter.")

# ==============================================================================
# 2. MOCK LLM GATEWAY
# ==============================================================================
# Denne klassen simulerer din faktiske LLMGateway for å gjøre skriptet kjørbart.
# I ditt prosjekt, vil du importere din faktiske LLMGateway her.

class MockLLMGateway:
    """
    En mock-klasse for å simulere LLM-kall.
    Den returnerer en forhåndsdefinert JSON-struktur for å teste arbeidsflyten.
    """
    async def generate_structured(self, prompt: str, response_schema: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        print("\n--- Kaller MockLLMGateway ---")
        print(f"Temperatur: {kwargs.get('temperature', 'N/A')}")
        
        # Simulerer at LLM-en fyller ut data basert på input-teksten
        # I en ekte applikasjon ville dette vært et nettverkskall til OpenAI/Azure e.l.
        raw_text_from_prompt = prompt.split("Tekstutdrag som skal analyseres:")[1].split("Din oppgave:")[0].strip()

        # Enkel logikk for å returnere en gyldig, men simpel, JSON-respons
        mock_response = {
            "chunk_id": str(uuid.uuid4()),
            "document_type": "instruks",
            "source_document_name": "Instruks_oslomodellen.pdf",
            "source_page": 1,
            "source_paragraph": 2,
            "status": "aktiv",
            "version": "1.0",
            "chunk_level": "regel",
            "section_number": "4.1",
            "title": "Seriøsitetskrav for små anskaffelser",
            "content_text": raw_text_from_prompt,
            "summary": "Dette er en LLM-generert oppsummering av tekstutdraget.",
            "actors": ["Oppdragsgiver", "Leverandør"],
            "risk_context": ["arbeidslivskriminalitet", "sosial_dumping"],
            "semantic_tags": ["seriøsitetskrav", "risiko"],
            "keywords": ["krav A-E", "risiko", "sosial dumping"],
            "key_values_and_thresholds": {"beløpsgrense_min": 100000, "beløpsgrense_max": 500000},
            "requirement_codes": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
            "applies_to_categories": ["bygge", "anlegg", "tjeneste"]
        }
        
        # Returner en subsett av felter for å sikre at validering med default-verdier fungerer
        return {k: v for k, v in mock_response.items() if k in response_schema['properties']}


# ==============================================================================
# 3. CHUNK AGENT SCRIPT
# ==============================================================================

class ChunkAgent:
    """
    Agent for å prosessere tekst-chunks, berike dem med metadata via en LLM,
    og lagre resultatet i en strukturert tabell (CSV).
    """
    def __init__(self, llm_gateway):
        self.llm_gateway = llm_gateway
        # Hent JSON schema fra Pydantic-modellen én gang for gjenbruk
        self.response_schema = CompleteChunkMetadata.model_json_schema()

    def _build_prompt(self, raw_text: str) -> str:
        """Bygger en detaljert og robust prompt for LLM-en."""
        
        # Bruker f-strings for å enkelt sette inn schema og tekst
        return f"""
Du er en ekspert på å analysere juridiske og administrative dokumenter for Oslo kommune. 
Din oppgave er å lese et tekstutdrag, analysere det i dybden, og fylle ut et JSON-objekt basert på Pydantic-modellen som er spesifisert under \"Målformat\".

**Målformat (JSON Schema):**
{json.dumps(self.response_schema, indent=2)}

Instruksjoner:
	1	Analyser teksten nøye.
	2	Trekk ut all relevant informasjon for å fylle ut feltene i JSON-objektet.
	3	Vær nøyaktig. Hvis informasjon for et felt ikke finnes i teksten, utelat feltet (dersom det er valgfritt) eller bruk en fornuftig standardverdi.
	4	Din respons MÅ være et rent JSON-objekt som kan valideres mot schemaet ovenfor. Ikke inkluder noe annet tekst eller forklaringer.


Tekstutdrag som skal analyseres: {raw_text}

Din oppgave: Returner ETT komplett JSON-objekt som representerer denne teksten, i henhold til Pydantic-modellen.
"""

    async def process_csv(self, input_filepath: str, output_filepath: str):
        """
        Leser en CSV-fil, prosesserer rader med status 'pending', og lagrer 
        resultatet til en ny CSV-fil.
        """
        try:
            df = pd.read_csv(input_filepath)
        except FileNotFoundError:
            print(f"Feil: Finner ikke filen {input_filepath}")
            return

        # Sørg for at output-kolonnene finnes
        if 'llm_output_json' not in df.columns:
            df['llm_output_json'] = None
        if 'qa_notes' not in df.columns:
            df['qa_notes'] = None

        # Iterer kun gjennom rader som trenger prosessering
        for index, row in df[df['status'] == 'pending'].iterrows():
            print(f"\nProsesserer rad {index} (chunk_id: {row['chunk_id']})...")
            
            raw_text = row['raw_text']
            prompt = self._build_prompt(raw_text)
            
            try:
                # Kall LLM-en
                structured_response = await self.llm_gateway.generate_structured(
                    prompt=prompt,
                    response_schema=self.response_schema,
                    purpose="metadata_extraction",
                    temperature=0.1
                )
                
                # Valider responsen mot Pydantic-modellen
                try:
                    CompleteChunkMetadata.model_validate(structured_response)
                    df.loc[index, 'llm_output_json'] = json.dumps(structured_response, ensure_ascii=False)
                    df.loc[index, 'status'] = 'processed'
                    print(f"Suksess for rad {index}.")
                except ValidationError as e:
                    df.loc[index, 'status'] = 'validation_error'
                    df.loc[index, 'qa_notes'] = f"Pydantic valideringsfeil: {e}"
                    print(f"Valideringsfeil for rad {index}: {e}")

            except Exception as e:
                df.loc[index, 'status'] = 'llm_error'
                df.loc[index, 'qa_notes'] = f"Feil under LLM-kall: {e}"
                print(f"Feil under prosessering av rad {index}: {e}")
        
        # Lagre den oppdaterte DataFrame til en ny fil
        df.to_csv(output_filepath, index=False)
        print(f"\nProsessering fullført. Resultatet er lagret i {output_filepath}")

# ==============================================================================
# 4. HOVED-BLOKK FOR Å KJØRE SKRIPTET
# ==============================================================================
async def main():
    """Hovedfunksjon for å sette opp og kjøre agenten."""
    # --- Oppsett av test-data ---
    input_csv_path = "chunks_to_process.csv"
    output_csv_path = "chunks_processed.csv"

    # Lag en eksempel-CSV for testing
    test_data = {
        'chunk_id': [str(uuid.uuid4()), str(uuid.uuid4())],
        'source_document': ['Instruks_oslomodellen.pdf', 'Byrådssak_klima_bygg_anlegg.pdf'],
        'page': [1, 6],
        'paragraph': [4, 2],
        'raw_text': [
            "I bygge-, anleggs- og tjenesteanskaffelser fra kr 100 000 til kr 500 000 skal krav A-E alltid benyttes. Krav F-T skal benyttes ved risiko for arbeidslivskriminalitet og sosial dumping.",
            "Det foreslås at virkeområdet for standardkravene til transport utvides, ved at beløpsgrensen senkes fra kr 500 000 til kr 100 000."
        ],
        'status': ['pending', 'pending']
    }
    pd.DataFrame(test_data).to_csv(input_csv_path, index=False)
    print(f"Opprettet test-fil: {input_csv_path}")

    # --- Initialisering og kjøring ---
    # Bytt ut MockLLMGateway med din faktiske gateway
    llm_gateway = MockLLMGateway() 

    agent = ChunkAgent(llm_gateway=llm_gateway)

    await agent.process_csv(
        input_filepath=input_csv_path,
        output_filepath=output_csv_path
    )

    # --- Vis resultatet ---
    print("\n--- Innhold i output-fil ---")
    processed_df = pd.read_csv(output_csv_path)
    print(processed_df.to_string(index=False))

if __name__ == "__main__":
    import asyncio
    # Kjører den asynkrone main-funksjonen
    asyncio.run(main())
