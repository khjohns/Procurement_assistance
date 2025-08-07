# Bygg en mer robust prompt
        # MERK: goal.context inneholder den opprinnelige forespørselen, 
        # mens current_state inneholder resultater fra utførte handlinger.
        prompt = f"""Du er en metodisk AI-orkestrator. Din oppgave er å analysere en situasjon og planlegge nøyaktig ett neste steg for å nå et mål. Følg disse instruksjonene slavisk:

1.  **Analyser Målet:** Forstå hva sluttresultatet skal være.
2.  **Analyser Datagrunnlaget:** Se på `INITIAL_DATA` for den opprinnelige konteksten og `CURRENT_STATE` for resultater av tidligere handlinger.
3.  **Vurder Verktøy:** Se på listen over `AVAILABLE_TOOLS` og deres beskrivelser.
4.  **Velg Neste Handling:** Velg det *eneste* verktøyet som er det mest logiske neste steget.
5.  **Fyll ut Parametre:** Hent all nødvendig data for verktøyets parametere fra `INITIAL_DATA` eller `CURRENT_STATE`. Dette er kritisk. `parameters`-feltet kan ikke være tomt hvis verktøyet krever input.
6.  **Formuler Resonnement:** Forklar kort hvorfor du valgte akkurat dette verktøyet.
7.  **Svar KUN med JSON:** Din respons må være et rent JSON-objekt, uten ekstra tekst før eller etter.

---
**EKSEMPEL PÅ TANKEPROSESS:**
* **Mål:** Behandle en anskaffelse.
* **Tilstand:** `procurementId` er `null`, ingen triagering utført.
* **Data:** `INITIAL_DATA` inneholder `name`, `value`, `description`.
* **Logisk neste steg:** Første steg er alltid å opprette saken. Verktøyet `database.create_procurement` passer perfekt.
* **Parametre:** Jeg henter `name`, `value`, `description` fra `INITIAL_DATA` og putter dem i `parameters`-objektet.
* **JSON-svar:**
    ```json
    {{
      "method": "database.create_procurement",
      "parameters": {{
        "name": "Innkjøp av nye møbler",
        "value": 10000,
        "description": "Erstatte stoler i kantina."
      }},
      "reasoning": "Første steg er å opprette anskaffelsessaken i databasen for å få en unik ID.",
      "expected_outcome": "En ny sak blir opprettet og en procurementId blir returnert."
    }}
    ```
---

**DATA FOR DENNE OPPGAVEN:**

<GOAL>
{context.goal.description}
</GOAL>

<SUCCESS_CRITERIA>
{json.dumps(context.goal.success_criteria, indent=2)}
</SUCCESS_CRITERIA>

<INITIAL_DATA>
{json.dumps(context.goal.context, indent=2)}
</INITIAL_DATA>

<CURRENT_STATE>
{json.dumps(context.current_state, indent=2)}
</CURRENT_STATE>

<AVAILABLE_TOOLS>
{tools_description}
</AVAILABLE_TOOLS>

<EXECUTED_ACTIONS>
{execution_summary}
</EXECUTED_ACTIONS>

Svar nå KUN med ett enkelt JSON-objekt basert på dataene over.
"""

***
Hvorfor dette er bedre:

XML-tags (<GOAL>, etc.): 
Gjør det krystallklart for modellen hvilke deler av prompten som er data og
 hvilke som er instruksjoner.

Trinnvise Instruksjoner: 
Bryter ned resonneringsoppgaven i en logisk rekkefølge som modellen må følge.
Steg 5 er spesielt viktig for å løse parameter-problemet.

Eksempel ("Few-shot"): 
Ved å gi et høykvalitets-eksempel på både tankeprosessen og det forventede JSON-svaret,
lærer vi modellen nøyaktig hvordan den skal oppføre seg.
***