# chunk_agent.py med integrert dokument-prosessering, "Analytiker" og "Manager" med endelig JSON-output

import pandas as pd
import json
import uuid
import os
import re
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ValidationError
from enum import Enum
from src.tools.llm_gateway import LLMGateway # Antar at denne er i din src-mappe
from dotenv import load_dotenv

from src.models.specialized_models import OslomodellMetadata # Hovedmodellen for validering

from pypdf import PdfReader

load_dotenv()

# ==============================================================================
# 1. DOCUMENT PROCESSOR
# ==============================================================================
class DocumentProcessor:
    """
    En klasse for å lese kildedokumenter (PDF) og dele dem opp i
    tekst-chunks.
    """
    def _read_pdf_text_with_metadata(self, pdf_filepath: str) -> List[Dict[str, Any]]:
        """
        Leser tekst fra en PDF-fil og samler chunks sammen med
        tilhørende sidetall.
        """
        extracted_data = []
        try:
            with open(pdf_filepath, 'rb') as f:
                reader = PdfReader(f)
                for page_num, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        # Deler opp tekst per avsnitt (eller en annen meningsfull separator)
                        paragraphs = self._chunk_by_top_level_sections(page_text)
                        for para_num, paragraph_text in enumerate(paragraphs, start=1):
                            extracted_data.append({
                                "text": paragraph_text,
                                "page": page_num,
                                "paragraph": para_num
                            })
        except FileNotFoundError:
            raise FileNotFoundError(f"Feil: Filen '{pdf_filepath}' ble ikke funnet.")
        except Exception as e:
            raise Exception(f"En feil oppstod under lesing av PDF-en: {e}")
        
        return extracted_data

    # --- CHUNKING-METODER ---

    def _chunk_by_fixed_size(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Metode 1: Enkel oppdeling etter fast størrelse."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def _chunk_by_top_level_sections(self, text: str) -> List[str]:
        """
        Deler opp teksten i hovedseksjoner basert på toppnivå-overskrifter (f.eks. '1.', '2.').
        
        Dette regex-mønsteret er justert for å unngå splitting på underpunkter.
        """
        # Dette regex-mønsteret ser kun etter et linjeskift etterfulgt av et tall og punktum,
        # som ikke er umiddelbart etterfulgt av et annet tall og punktum.
        separators = r'(?=\n\s*\d+\.\s+)'
        chunks = re.split(separators, text)
        
        cleaned_chunks = [chunk.strip() for chunk in chunks if chunk.strip()]

        return cleaned_chunks

    def _chunk_recursively(self, text: str, separators: List[str], chunk_size: int) -> List[str]:
        """Metode 3: Rekursiv oppdeling (Anbefalt)."""
        # Dette er en forenklet versjon av den populære "RecursiveCharacterTextSplitter".
        final_chunks = []
        
        # Start med den største separatoren (avsnitt)
        current_separator = separators[0]
        splits = text.split(current_separator)
        
        good_splits = []
        for s in splits:
            if len(s) < chunk_size:
                good_splits.append(s)
            else:
                # Hvis en split er for stor, gå ett nivå dypere i rekursjonen
                if len(separators) > 1:
                    deeper_chunks = self._chunk_recursively(s, separators[1:], chunk_size)
                    good_splits.extend(deeper_chunks)
                else:
                    # Nådd bunnen av rekursjonen, bare legg til den store chunken
                    good_splits.append(s)
        
        # Slå sammen små chunks for å fylle chunk_size
        current_chunk = ""
        for s in good_splits:
            if len(current_chunk) + len(s) + len(current_separator) > chunk_size and current_chunk:
                final_chunks.append(current_chunk)
                current_chunk = ""
            
            if current_chunk:
                current_chunk += current_separator + s
            else:
                current_chunk = s
        
        if current_chunk:
            final_chunks.append(current_chunk)
            
        return final_chunks

    def process_pdf_to_dataframe(self, pdf_filepath: str) -> pd.DataFrame:
        """
        Hovedfunksjon som tar en PDF, leser den, deler den opp i chunks,
        og returnerer en DataFrame klar for ChunkAgent.
        """
        print(f"Prosesserer PDF: '{pdf_filepath}'...")
        document_chunks = self._read_pdf_text_with_metadata(pdf_filepath)

        filtered_chunks = []
        for chunk in document_chunks:
            # Skip chunks som kun er titler (korte, ofte på første side)
            if chunk['page'] == 1 and len(chunk['text'].strip()) < 150:
                print(f"Dropper kort chunk fra side 1: '{chunk['text'][:50]}...'")
                continue
            filtered_chunks.append(chunk)
        document_chunks = filtered_chunks
        
        """
        # NYTT: Dropp første chunk (tittelen)
        if len(document_chunks) > 0:
            print(f"Dropper første chunk (tittel): '{document_chunks[0]['text'][:100]}...'")
            document_chunks = document_chunks[1:]
        """
        
        document_name = os.path.basename(pdf_filepath)
        
        # Bygg DataFrame fra den berikede listen av chunks
        data = {
            "chunk_id": [f"{document_name.split('.')[0]}-{uuid.uuid4()}" for _ in document_chunks],
            "source_document": [document_name] * len(document_chunks),
            "page": [d['page'] for d in document_chunks],
            "paragraph": [d['paragraph'] for d in document_chunks],
            "raw_text": [d['text'] for d in document_chunks],
            "status": ["pending"] * len(document_chunks)
        }
        
        print(f"Dokumentet ble delt opp i {len(document_chunks)} chunks (etter å ha droppet tittelen).")
        
        return pd.DataFrame(data)

# ==============================================================================
# 2. POST-PROCESSOR FOR DATA CLEANING
# ==============================================================================

class PostProcessor:
    """En klasse for å rydde og standardisere LLM-generert JSON."""

    OPERATOR_MAP = {
        # Standard operatorer fra enumen
        ConditionOperator.GT.value: ConditionOperator.GT.value,
        ConditionOperator.GTE.value: ConditionOperator.GTE.value,
        ConditionOperator.LT.value: ConditionOperator.LT.value,
        ConditionOperator.LTE.value: ConditionOperator.LTE.value,
        ConditionOperator.EQ.value: ConditionOperator.EQ.value,
        ConditionOperator.IN.value: ConditionOperator.IN.value,
        ConditionOperator.NOT_IN.value: ConditionOperator.NOT_IN.value,
        ConditionOperator.BETWEEN.value: ConditionOperator.BETWEEN.value,
        ConditionOperator.CONTAINS.value: ConditionOperator.CONTAINS.value,
        
        # Synonymer
        "greater_than": ConditionOperator.GT.value,
        "gt": ConditionOperator.GT.value,
        "less_than": ConditionOperator.LT.value,
        "lt": ConditionOperator.LT.value,
        "equals": ConditionOperator.EQ.value,
        "eq": ConditionOperator.EQ.value,
        "er": ConditionOperator.EQ.value,
        "er_lik": ConditionOperator.EQ.value,
        "greater_than_or_equal_to": ConditionOperator.GTE.value,
        "gte": ConditionOperator.GTE.value,
        "less_than_or_equal_to": ConditionOperator.LTE.value,
        "lte": ConditionOperator.LTE.value,
        "er_i": ConditionOperator.IN.value
    }
    def clean(self, data: dict) -> dict:
        """Kjører alle opprydningsfunksjoner på et JSON-objekt."""
        if not isinstance(data, dict):
            return data
            
        data = self._normalize_operators_in_rulesets(data)
        # Her kan du legge til flere fremtidige opprydningsmetoder
        # data = self._another_cleaning_function(data)
        return data

    def _normalize_operators_in_rulesets(self, data: dict) -> dict:
        """Går gjennom rule_sets og standardiserer operatorer."""
        if "rule_sets" in data and isinstance(data["rule_sets"], list):
            for rule_set in data["rule_sets"]:
                if "conditions" in rule_set and isinstance(rule_set["conditions"], list):
                    for condition in rule_set["conditions"]:
                        if "operator" in condition:
                            op = condition["operator"].lower()
                            # Slå opp i kartet og erstatt med standardverdi,
                            # eller behold originalen hvis den ikke finnes.
                            condition["operator"] = self.OPERATOR_MAP.get(op, op)
        return data

# ==============================================================================
# 2. CHUNK AGENT MED INTEGRERT MANAGER
# ==============================================================================

class ChunkAgent:
    """
    En to-stegs agent som først analyserer individuelle chunks ("Analytiker")
    og deretter gjennomgår dem i grupper for å sikre konsistens og bygge
    relasjoner ("Manager").
    """
    def __init__(self, llm_gateway: LLMGateway):
        self.llm_gateway = llm_gateway
        self.response_schema = OslomodellMetadata.model_json_schema()
        print(f"Lengden på JSON-skjemaet for analytiker er: {len(json.dumps(self.response_schema))}")

    # --- Bygging av Prompts ---

    def _build_analyst_prompt(self, raw_text: str, chunk_id: str, source_document: str, page: int, paragraph: int) -> str:
        """
        Bygger en token-effektiv prompt for "Analytiker"-LLM-en
        ved å bruke et minimalt, hardkodet schema-eksempel.
        """
        # Dette minimale schemaet sendes til LLM-en for å spare tokens
        minimal_schema_example = """
{
  "chunkId": "string",
  "sourceDocumentName": "string",
  "title": "string",
  "contentText": "string",
  "summary": "string",
  "risk_level": ["lav", "moderat", "høy"],
  "requirement_codes": ["A", "B", "C"],
  "conditions": [
    {
      "description": "En beskrivelse av regelen",
      "field": "kontraktsverdi",
      "operator": ">",
      "value": 500000
    }
  ]
}
"""
        return f"""
Du er en dataanalytiker som konverterer tekst til et strukturert JSON-objekt.

**Strenge regler:**
1.  **100% Schema-validering:** Alle nøkler fra Målformatet MÅ inkluderes. For manglende data, bruk `null`, `[]`, eller {{}}`.
2.  **Rene verdier:** Tall skal være `int` (f.eks. `500000`), ikke `"500 000 kr"`.
3.  **Struktur for maskinlesbarhet:**
    * **`requirement_codes`:** I hovedlisten skal du inkludere ALLE koder som er nevnt i hele tekst-chunken.
    * **`rule_sets`:** # ENDRET HER: Ny og viktigere regel.
        - **Grupper ALLTID** logisk relaterte betingelser sammen i ett scenario.
        - Hver hovedregel fra teksten (f.eks. fra punktene 4.1, 4.2) skal være **ett separat objekt** i `rule_sets`-listen.
        - I `applies_to_codes` inni et `rule_set` skal du kun liste kodene som gjelder for **akkurat det scenarioet**.
4.  * **Operatorer:** Bruk KUN følgende standardiserte operatorer: 
      `>`, `<`, `=`, `>=`, `<=`, `in`, `between`, `not_in`.
5.  **Bruk gitt input:** Ikke endre `chunk_id`, `source_document_name` osv.
6.  **Risikonivå (`risk_level`):** Hvis teksten kun sier "risiko" (uten å spesifisere nivå), skal listen inneholde ALLE nivåer: `["lav", "moderat", "høy"]`.

**Input-data:**
-   chunk_id: {chunk_id}
-   source_document_name: {source_document}
-   source_page: {page}
-   source_paragraph: {paragraph}

**Eksempel på målformat:**
{minimal_schema_example}

**Tekst som skal analyseres:**
{raw_text}

**Din oppgave:**
Returner kun ett validert JSON-objekt basert på teksten og input-dataene.

"""

    def _build_manager_prompt(self, chunk_list: List[Dict[str, Any]]) -> str:
        """Bygger prompten for "Manager"-LLM-en."""
        chunk_list_json = json.dumps(chunk_list, indent=2, ensure_ascii=False)
        return f"""
Du er en hyper-nøyaktig senior dataarkitekt og kvalitetssikrer.
Din oppgave er å gjennomgå en liste med JSON-objekter som er generert av en junior-analytiker. Du skal se på dem som en helhet og forbedre dem.

**Regler for gjennomgang:**
1.  **Sikre konsistens:** Sørg for at like konsepter (f.eks. verditerskler, kategorier) er navngitt og strukturert på nøyaktig samme måte i alle objektene.
2.  **Bygg relasjoner:** Dette er din viktigste oppgave. Analyser `section_number` og innhold for å fylle ut:
    - `parent_chunk_id`: Hvis f.eks. en chunk er "4.1a", skal `parent_chunk_id` peke på chunk "4.1".
    - `related_chunk_ids`: Hvis flere chunks omhandler samme overordnede tema (f.eks. unntak i punkt 7), skal de peke til hverandre.
3.  **Korriger åpenbare feil:** Hvis du ser en logisk brist eller en klar feiltolkning i ett objekt basert på konteksten fra de andre, korriger det.

**Input (Liste med JSON-objekter fra junior-analytiker):**
{chunk_list_json}

**Din oppgave:**
Returner den fullstendige listen med de samme JSON-objektene, men nå korrigert og med relasjonsfeltene (`parent_chunk_id`, `related_chunk_ids`) korrekt utfylt. Returner KUN den endelige JSON-listen. Ikke noe annet.
"""

    # --- Kjøring av faser ---

    async def _run_analyst_phase(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Kjører "analytiker"-fasen..."""
        processed_chunks = []
        for index, row in df.iterrows():
            print(f"\nAnalytiker prosesserer rad {index} (chunk_id: {row['chunk_id']})...")
            
            # Bygger den optimaliserte prompten
            prompt = self._build_analyst_prompt(
                raw_text=row['raw_text'],
                chunk_id=row['chunk_id'],
                source_document=row['source_document'],
                page=row['page'],
                paragraph=row['paragraph']
            )
            
            try:
                structured_response = await self.llm_gateway.generate_structured(
                    prompt=prompt,
                    response_schema=self.response_schema,
                    temperature=0.1
                )
                
                cleaned_response = self.post_processor.clean(structured_response)
            
                # Valider den ryddede responsen
                OslomodellMetadata.model_validate(cleaned_response)
                
                processed_chunks.append(cleaned_response) # Legg til den ryddede versjonen
                print(f"Suksess for rad {index}.")

            except (ValidationError, Exception) as e:
                print(f"FEIL under analytiker-fase for rad {index}: {e}")
        
        return processed_chunks

    async def _run_manager_phase(self, analyst_outputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Kjører "manager"-fasen på en liste med chunks."""
        print(f"\n{'='*20}\nManager starter gjennomgang av {len(analyst_outputs)} chunks...\n{'='*20}")
        if not analyst_outputs:
            return []

        prompt = self._build_manager_prompt(analyst_outputs)
        try:
            # For en LLM som kan returnere en liste direkte
            manager_response = await self.llm_gateway.generate_structured(
                prompt=prompt,
                response_schema={"type": "array", "items": self.response_schema},
                purpose="deep_thinking",
                temperature=0.0 # Manageren skal være presis, ikke kreativ
            )
            # Dobbeltsjekk at vi fikk en liste tilbake
            if isinstance(manager_response, list):
                cleaned_manager_response = [self.post_processor.clean(item) for item in manager_response]
                print("Manager-gjennomgang fullført med suksess.")
                return cleaned_manager_response
            else:
                print("FEIL: Manager returnerte ikke en liste. Returnerer opprinnelig data.")
                return analyst_outputs
        except Exception as e:
            print(f"FEIL under manager-fase: {e}. Returnerer opprinnelig data.")
            return analyst_outputs

    # --- Hoved-pipeline --- #

    async def run_pipeline(self, csv_for_agent_path: str, output_filepath: str, batch_size: int = 10):
        """
        Kjører hele to-stegs pipelinen:
        1. Leser input-CSV.
        2. Kjører analytiker-fase på alle rader i batcher.
        3. Kjører manager-fase på hver batch.
        4. Lagrer det endelige resultatet som én JSON-fil.
        """
        try:
            df = pd.read_csv(csv_for_agent_path, delimiter='|', encoding='utf-8')
            #   Ingen manipulering nødvendig - vi bruker dataframen som den ble lagret
            df_to_process = df[df['status'] == 'pending']
        except FileNotFoundError:
            print(f"FEIL: Finner ikke input-filen '{csv_for_agent_path}'")
            return

        final_results = []
        # Prosesser i batcher
        for i in range(0, len(df_to_process), batch_size):
            batch_df = df_to_process.iloc[i:i+batch_size]
            print(f"\n--- Prosesserer Batch {i//batch_size + 1} ---")
            
            # 1. Analytiker-fase
            analyst_outputs = await self._run_analyst_phase(batch_df)
            
            # 2. Manager-fase
            manager_outputs = await self._run_manager_phase(analyst_outputs)
            
            final_results.extend(manager_outputs)

        # 3. Lagre det endelige, rene JSON-resultatet
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n\nPipeline fullført. Det endelige, korrigerte resultatet er lagret i '{output_filepath}'")

# ==============================================================================
# 3. HOVED-BLOKK FOR Å KJØRE HELE PIPELINEN
# ==============================================================================

async def main():
    # --- STEG 1: Pre-prosessering --- #
    
    source_pdf_path = "Instruks_oslomodellen.pdf" # PDF-filen du vil prosessere
    csv_for_agent_path = "chunks_for_agent_input.csv" # Mellomlagringsfil
    final_json_output_path = "oslomodell_chunks_final.json" # Endelig resultat

    # Sjekk om kilde-PDF finnes
    if not os.path.exists(source_pdf_path):
        print(f"FEIL: Kilde-PDF '{source_pdf_path}' ble ikke funnet. Kan ikke kjøre.")
        return

    processor = DocumentProcessor()
    
    try:
        input_df = processor.process_pdf_to_dataframe(pdf_filepath=source_pdf_path)
    except (FileNotFoundError, ImportError) as e:
        print(f"Kritisk feil: {e}")
        return

    print("\n--- Kvalitetskontroll: Oppdeling av dokument ---")
    print(f"Dokumentet ble delt opp i {len(input_df)} chunks.")
    print("Her er et utdrag fra de tre første bitene:")
    for i, row in input_df.head(10).iterrows():
        print(f"  Chunk {i+1}: '{row['raw_text'][:300].strip()}...'")

    proceed = input("\nØnsker du å fortsette og lagre disse chunksene for agent-prosessering? (ja/nei): ").lower()
    if proceed not in ['ja', 'j', 'yes', 'y']:
        print("Avbryter prosessen.")
        return
    
    # Lagre til en CSV-fil som ChunkAgent kan lese
    input_df.to_csv(csv_for_agent_path, index=False, sep='|', encoding='utf-8')
    print(f"Input-fil for agenten er lagret som '{csv_for_agent_path}'.")

    # --- STEG 2: Agent-prosessering ---
    llm_gateway = LLMGateway()
    agent = ChunkAgent(llm_gateway=llm_gateway)

    await agent.run_pipeline(
        csv_for_agent_path=csv_for_agent_path,
        output_filepath=final_json_output_path,
        batch_size=3 # Setter en batch-størrelse for manageren
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())