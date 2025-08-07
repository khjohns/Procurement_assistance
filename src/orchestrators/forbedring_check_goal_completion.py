prompt = f"""Din oppgave er å vurdere om et mål er fullført ved å sammenligne suksesskriteriene med den nåværende tilstanden.

1.  Les hvert enkelt punkt i `<SUCCESS_CRITERIA>`.
2.  For hvert kriterium, sjekk om `<CURRENT_STATE>` inneholder bevis for at det er oppfylt.
    - Vær streng: `triage_completed: true` er ikke det samme som `triage_saved: true`. Se etter det eksakte beviset.
3.  Konkluder om **alle** kriteriene er oppfylt.
4.  Svar KUN med et JSON-objekt.

<GOAL>
{context.goal.description}
</GOAL>

<SUCCESS_CRITERIA>
{json.dumps(context.goal.success_criteria, indent=2)}
</SUCCESS_CRITERIA>

<CURRENT_STATE>
{json.dumps(context.current_state, indent=2)}
</CURRENT_STATE>

Svar nå KUN med JSON-objektet.
"""

***
Hvorfor dette er bedre:

Direkte Instruksjoner: 
I stedet for å be modellen "vurdere", gir vi den en konkret oppgave: "sammenligne".

Streng Tolkning:
Instruksjonen "Vær streng: triage_completed: true er ikke det samme som triage_saved: true" 
er en kraftig teknikk som reduserer sjansen for at modellen tar snarveier og konkluderer feilaktig.
***