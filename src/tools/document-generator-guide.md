# 📄 Oslomodell Document Generator - Implementeringsguide

## Oversikt

Document Generator er et verktøy som automatisk genererer strukturerte anskaffelsesnotater basert på Oslomodell-vurderinger. Den produserer markdown-dokumenter med alle relevante krav, anbefalinger og oppfølgingspunkter.

## 📦 Komponenter

### 1. `oslomodell_document_generator.py`
Hovedklassen som genererer dokumenter. Inneholder:
- Mal for alle seriøsitetskrav (A-V)
- Strukturert dokumentgenerering
- Oppsummeringstabeller
- Metadata og sporbarhet

### 2. Output Format
Genererer markdown (.md) filer med:
- Anskaffelsesinformasjon
- Risikovurdering
- Komplett kravliste
- Underleverandørbegrensninger
- Lærlingkrav
- Aktsomhetsvurderinger
- Anbefalinger
- Oppfølgingspunkter

## 🚀 Implementering

### Steg 1: Installer Document Generator

**Ny fil:** `src/tools/oslomodell_document_generator.py`

Kopier innholdet fra `oslomodell_document_generator.py` artifact.

### Steg 2: Integrer med Orchestrator

**Oppdater:** `src/orchestrators/reasoning_orchestrator.py`

Legg til etter goal completion:

```python
# I achieve_goal metoden, etter goal.status = COMPLETED
if goal.status == GoalStatus.COMPLETED:
    # Generer dokument hvis Oslomodell er kjørt
    for exec in context.execution_history:
        if exec['action']['method'] == 'agent.run_oslomodell':
            from src.tools.oslomodell_document_generator import OslomodellDocumentGenerator
            
            generator = OslomodellDocumentGenerator("procurement_documents")
            procurement_data = context.current_state.get('request')
            oslomodell_result = exec['result']['result']
            
            if procurement_data and oslomodell_result:
                doc_path = generator.generate_document(
                    procurement_data,
                    oslomodell_result
                )
                logger.info(f"Generated document: {doc_path}")
                context.current_state['document_path'] = doc_path
            break
```

### Steg 3: Test Dokumentgenerering

```bash
# Kjør test som genererer eksempeldokumenter
python test_document_generation.py
```

Dette vil:
1. Kjøre Oslomodell-agent på 3 test-cases
2. Generere dokument for hver
3. Lage oppsummeringstabell
4. Lagre alt i `test_documents/` mappen

## 📋 Eksempel på Generert Dokument

```markdown
# Anskaffelsesnotat - Oslomodellen

**Generert:** 07.08.2025 kl. 22:30

---

## 1. Anskaffelsesinformasjon

**Navn:** Totalentreprise ny barnehage
**Verdi:** 35,000,000 NOK ekskl. mva
**Kategori:** Byggearbeider
**Varighet:** 18 måneder

**Beskrivelse:**
> Bygging av ny 6-avdelings barnehage med uteområder

---

## 2. Risikovurdering

**Vurdert risiko for arbeidslivskriminalitet:** 🔴 **HØY**

---

## 3. Påkrevde seriøsitetskrav

**Antall krav:** 22 stk
**Hjemmel:** Instruks for Oslo kommunes anskaffelser, punkt 4

### Kravliste:

#### Basiskrav (alltid påkrevd):
- **Krav A:** HMS-egenerklæring
- **Krav B:** Skatteattest
- **Krav C:** Bekreftelse på betaling av arbeidsgiveravgift
- **Krav D:** Bekreftelse på tegning av yrkesskadeforsikring
- **Krav E:** Bekreftelse på ansettelsesforhold

#### Tilleggskrav (basert på kategori/risiko):
- **Krav F-U:** [Full liste med beskrivelser]

#### Spesialkrav:
- **Krav V:** Lærlinger (over terskelverdi)

[...fortsetter med alle seksjoner...]
```

## 🔧 Tilpasninger

### Custom Templates

Du kan enkelt tilpasse maler ved å endre `krav_beskrivelser` dictionary:

```python
generator.krav_beskrivelser["A"] = "Din egen beskrivelse for krav A"
```

### Ekstra Seksjoner

Legg til egne seksjoner i `_generate_markdown_content`:

```python
# Legg til GDPR-seksjon for IT-prosjekter
if procurement.get('category') == 'it':
    lines.extend([
        "## X. GDPR og Datasikkerhet\n",
        "- [ ] Databehandleravtale påkrevd",
        "- [ ] Risikovurdering for personvern utført"
    ])
```

### Alternative Output-formater

For å generere andre formater (HTML, PDF):

```python
# HTML output
html_content = markdown2.markdown(content)

# PDF via weasyprint
from weasyprint import HTML
HTML(string=html_content).write_pdf('document.pdf')
```

## 📊 Bruksområder

1. **Automatisk dokumentasjon** - Hver anskaffelse får sitt notat
2. **Compliance-rapportering** - Vis at krav følges
3. **Mal for konkurransegrunnlag** - Basis for videre arbeid
4. **Revisjonsspor** - Dokumentasjon av vurderinger
5. **Opplæring** - Vise hvilke krav som gjelder når

## 🐛 Feilsøking

### Problem: "No module named 'oslomodell_document_generator'"
**Løsning:** Sjekk at filen er i riktig mappe (`src/tools/`)

### Problem: Manglende kravbeskrivelser
**Løsning:** Oppdater `krav_beskrivelser` dictionary med alle krav A-V

### Problem: Feil i markdown-formatering
**Løsning:** Test med markdown preview, sjekk spesialtegn

## ✅ Sjekkliste

- [ ] Document generator installert i `src/tools/`
- [ ] Test kjørt vellykket
- [ ] Output-mappe opprettet (`procurement_documents/`)
- [ ] Integrasjon med orchestrator (valgfritt)
- [ ] Tilpasset kravbeskrivelser om nødvendig

## 🎯 Neste Steg

1. **Integrer med frontend** - Vis genererte dokumenter i UI
2. **Legg til eksport** - PDF, Word, etc.
3. **Mal-bibliotek** - Forskjellige maler for ulike typer
4. **Versjonering** - Spor endringer over tid
5. **Signering** - Digital signatur for godkjenning

## 📝 Eksempel: Full Integrasjon

```python
# main.py med dokumentgenerering
async def process_procurement_with_document():
    # Kjør full orkestrering
    orchestrator = ReasoningOrchestrator(llm_gateway)
    context = await orchestrator.achieve_goal(goal)
    
    # Generer dokument automatisk
    if context.goal.status == GoalStatus.COMPLETED:
        from src.tools.oslomodell_document_generator import generate_from_orchestration
        
        doc_path = await generate_from_orchestration(context)
        print(f"📄 Dokument generert: {doc_path}")
        
        # Åpne i standard markdown-viewer
        import subprocess
        subprocess.run(["open", doc_path])  # macOS
        # subprocess.run(["xdg-open", doc_path])  # Linux
```

---

Med denne løsningen får du automatisk genererte, strukturerte notater som dokumenterer hele Oslomodell-vurderingen på en profesjonell måte!