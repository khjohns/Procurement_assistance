## Oslomodell-agenten

### Om agenten
Oslomodellagenten er en spesialistagent som skal analysere en anskaffelsen opp mot `Instruks for Oslo kommunes anskaffelser`. Det benyttes RAG med metadata (hybrid-rag). 

**Forhold til orkestrator og andre agenter:** Systemet består av orkestrator, triage_agent og oslomodell_agent. Triage_agent vil (etter planen) kalles etter oslomodell_agent for å vurdere klassifisering av anskaffelsen. Det må vurderes om vilkår for klassifisering av RØD, GUL, GRØNN må justeres noe nå som Oslomodell-agenten implementeres.

I første omgang (versjon 0.1) skal Oslomodell-agenten kunnskapsbase kun bestå av følgende punkter fra Instruksen:
* Pkt. 1 om Formål
* Pkt. 4 om Anvendelsesområde for Oslomodellens seriøsitetskrav
* Pkt. 5 om Begrensninger i bruk av underleverandører i vertikal kjede
* Pkt. 6 om Krav til bruk av lærlinger
* Pkt. 7 om Oslomodellens krav til aktsomhetsvurderinger for ansvarlig næringsliv

**Informasjonsgrunnlag**
* Hovedregelen er at agenten bruker sitt kunnskapsgrunnlag (RAG).
* Hvis det er nødvendig, kan agenten gi en konsis og kortfattet vurdering - **med forbehold** - om anskaffelsen innebærer en risiko for arbeidslivskriminalitet eller sosial dumping (se Instruksen pkt. 4).
* Hvis det er nødvendig, kan agenten gi en konsis og kortfattet vurdering - **med forbehold** - om anskaffelsen generelt sett innebærer en høy risiko for brudd på grunnleggende menneskerettigheter, arbeidstakerrettigheter og internasjonal humanitærrett, miljøødeleggelse eller korrupsjon i leverandørkjeden (se Instruksen pkt. 7).
* Informasjon om krav til lærlinger er hardkodet basert på følgende:
  * I alle kontrakter om bygge- og anleggsarbeider skal det stilles krav om at leverandøren og eventuelle underleverandører har lærlinger. For øvrige kontrakter har ikke agenten tilstrekkelig informasjon til å foreta en endelig konklusjon. Plikten gjelder for relevante kontrakter med en varighet på over tre måneder og en anslått verdi på over 1,75 millioner kroner ekskl.

**Input (JSON):** Et strukturert objekt fra orkestratoren med nøkkeldata om anskaffelsen. Kortfattet eksempel:
  ```json
  {
    "verdi_nok_eks_mva": 600000,
    "type": "tjenesteanskaffelse",
    "varighet_måneder": 4,
    "fagområder": ["renhold"]
  }

**Output (JSON):** En maskinlesbar "oppskrift" til orkestratoren.
  ```json
  {
    "status": "success",
    "vurdert_risiko_for_akrim": "høy",
    "påkrevde_seriøsitetskrav": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"],
    "anbefalt_antall_underleverandørledd": 1,
    "krav_om_lærlinger": {
      "status": true,
      "begrunnelse": "Verdi over statlig terskelverdi, varighet over 3 måneder og innenfor definert fagområde."
    },
    "handling_for_aktsomhetsvurdering": {
      "krav_utløst": true,
      "begrunnelse": "Anskaffelse over kr 500 000.",
      "begrunnelse": "..."
    }
  }
  ```

Det er gjennomført en PoC for Oslomodell-agenten i google-stack (utenfor dette prosjektet (Procurement assistance) med dynamisk agent-orkestrering mm.). Hovedskriptet ser du nedenfor. 
**NB! Agenten har en del funksjoner som ikke vil være relevant for vår del i denne omgang.**

Kjørelogg fra skriptet ser du også nedenfor. Denne var i høy grad vellykket. Output må trolig tilpasses noe til vårt prosjekt.

Agentens kunnskapsbase er også nedenfor. Denne vil brukes i vårt prosjektet. Andre chunks- og metadata-strategier vil utforskes senere.



### Google apps script (fra PoC)
```javascript
// ===================================================================
// HOVEDFUNKSJON FOR AGENT-LOGIKK
// ===================================================================
function agentRAGFlow() {
  // Endre gjerne dette spørsmålet for å teste ulike scenarioer
  const userQuery = "Hvilke krav gjelder for en bygge- og anleggskontrakt til 1.500.000 kr med 'Entreprenør AS' som leverandør?";
  Logger.log("AGENT STARTER med generelt spørsmål: " + userQuery);

  // --- TRINN 1: PLANLEGGING ---
  const planPrompt = `
    Du er en ekspert på Oslomodellen som skal fungere som en presis planlegger. 
    Analyser følgende bruker-spørsmål og lag en handlingsplan ved å identifisere kun de absolutt relevante temaene som må undersøkes.
    Brukerspørsmål: "${userQuery}"
    Følg disse stegene slavisk:
    1. Identifiser anskaffelsens verdi i norske kroner.
    2. Identifiser om anskaffelsen gjelder 'vare', 'tjeneste' eller 'bygge- og anleggskontrakt'.
    3. Bruk verdi og kontraktstype til å avgjøre hvilke temaer som er relevante.
    4. Hvis spørsmålet åpenbart ikke handler om anskaffelser (f.eks. 'ferieavvikling'), returner en tom liste i planen.
    Gyldige temaer du kan inkludere i planen er: "Seriøsitetskrav", "Aktsomhetsvurderinger", "Lærlinger".
    Returner KUN et gyldig JSON-objekt med en nøkkel "plan" som inneholder listen over de relevante temaene.
  `;
  const planResponse = callGeminiForJson(planPrompt);
  
  if (planResponse && planResponse.plan && Array.isArray(planResponse.plan) && planResponse.plan.length > 0) {
    const plan = planResponse.plan;
    Logger.log("Agentens plan: Undersøker temaene " + plan.join(', '));

    // --- TRINN 2: HENT INTERN KONTEKST ---
    let internalContext = "";
    const queryEmbedding = createEmbedding(userQuery); 
    for (const tema of plan) {
      Logger.log("Henter kontekst for tema: " + tema);
      const searchResponse = UrlFetchApp.fetch(SUPABASE_URL + '/rest/v1/rpc/match_documents_filtered', {
        method: 'post',
        headers: { 'apikey': SUPABASE_ANON_KEY, 'Authorization': 'Bearer ' + SUPABASE_ANON_KEY, 'Content-Type': 'application/json' },
        payload: JSON.stringify({ query_embedding: queryEmbedding, match_threshold: 0.1, match_count: 1, filter_tema: tema })
      });
      const searchResults = JSON.parse(searchResponse.getContentText());
      if (searchResults && searchResults.length > 0) {
        internalContext += `--- Kontekst for tema: "${tema}" ---\n`;
        for (const result of searchResults) {
          internalContext += result.content + "\n";
        }
      }
    }
    Logger.log("All intern kontekst hentet.");

    // ERSTATT DEN GAMLE reasoningPrompt MED DENNE:
  const reasoningPrompt = `
    Du er en senioranalytiker som skal dekomponere et komplekst problem og lage en plan for informasjonsinnhenting.

    Brukerspørsmål: "${userQuery}"
    Intern kontekst: "${internalContext}"

    Følg disse resonnerings-stegene:
    1.  **Dekomponer Anskaffelsen:** Basert på brukerspørsmålet, identifiser de implisitte komponentene.
        * Hvis det er en 'bygge- og anleggskontrakt', inkluderer dette materialer som 'stål', 'sement', 'elektronikk'.
        * Hvis det er en 'bygge- og anleggskontrakt', inkluderer dette fagområder som 'tømrerfaget', 'rørleggerfaget', 'elektrofag'.

    2.  **Identifiser Kunnskapshull:** Sammenlign dekomponeringen med den interne konteksten.
        * Trenger du å vurdere risiko for de identifiserte materialene?
        * Trenger du å sjekke om de identifiserte fagområdene har behov for lærlinger?
        * Nevner konteksten en 'statlig terskelverdi' uten å spesifisere den?

    3.  **Lag en Verktøy-plan:** Basert på kunnskapshullene, lag en liste over nødvendige verktøykall.

    Tilgjengelige verktøy: 'dfo_risk_check', 'apprenticeship_check', 'regulation_fetch', 'none'.

    Returner et JSON-objekt med en nøkkel "tool_plan" som er en liste over verktøy som skal kalles.
    Eksempel: {"tool_plan": [{"tool_name": "dfo_risk_check", "tool_input": "stål"}, {"tool_name": "apprenticeship_check", "tool_input": "tømrerfaget"}, {"tool_name": "regulation_fetch", "tool_input": "forskrift om lærlinger"}]}
  `;
    
    const toolPlanResponse = callGeminiForJson(reasoningPrompt);
    let externalContext = "";

    if (toolPlanResponse && toolPlanResponse.tool_plan && toolPlanResponse.tool_plan.length > 0) {
      for (const toolCall of toolPlanResponse.tool_plan) {
        Logger.log(`Agenten valgte verktøy: ${toolCall.tool_name} med input: ${toolCall.tool_input}`);
        if (toolCall.tool_name === "dfo_risk_check") {
          externalContext += dfoRiskCheckTool(toolCall.tool_input);
        } else if (toolCall.tool_name === "apprenticeship_check") {
          externalContext += checkApprenticeshipRegistryTool(toolCall.tool_input);
        } else if (toolCall.tool_name === "regulation_fetch") {
          externalContext += fetchRegulationTool(toolCall.tool_input);
        }
      }
    } else {
      Logger.log("Agenten konkluderte med at ingen eksterne verktøy var nødvendig.");
    }

    // --- TRINN 3: SYNTESE ---
    const finalPrompt = `
      Du er en ekspert-assistent som skal gi et helhetlig og presist svar.
      Bruk all tilgjengelig kontekst og siter kildene dine tydelig.

      Spesialinstruks for tolkning: Tolk 'Instruks for Oslomodellen' i lys av den eksterne 'Forskrift om offentlige anskaffelser'. Instruksen kan være strengere, men aldri mildere.

      Opprinnelig spørsmål: "${userQuery}"
      Kontekst fra Internt Regelverk: ${internalContext}
      Kontekst fra Eksterne Kilder: ${externalContext}

      Strukturer svaret ditt i henhold til de relevante kravene.
      **Avslutt med en kort, overordnet vurdering og en konkluderende anbefaling for denne spesifikke anskaffelsen.**
    `;
    
    const finalAnswer = callGemini(finalPrompt);
    Logger.log("--- AGENTENS ENDELIGE SVAR ---");
    Logger.log(finalAnswer);

  } else {
    Logger.log("Planen er tom eller ugyldig. Svarer høflig til brukeren.");
    const finalAnswer = callGemini(`Brukeren stilte et spørsmål som er utenfor kontekst for anskaffelser. Svar høflig at du kun kan svare på spørsmål relatert til Oslomodellens krav til anskaffelser. Spørsmål: "${userQuery}"`);
    Logger.log("--- AGENTENS ENDELIGE SVAR ---");
    Logger.log(finalAnswer);
    return; 
  }
}

// ===================================================================
// NØDVENDIGE HJELPEFUNKSJONER OG VERKTØY
// ===================================================================

/**
 * Hjelpefunksjon for å lage embeddings.
 */
function createEmbedding(text) {
  const embeddingUrl = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-exp-03-07:embedContent?key=' + GOOGLE_AI_API_KEY;
  const payload = {
      model: "models/gemini-embedding-exp-03-07",
      content: { parts: [{ "text": text }] },
      output_dimensionality: 768 
  };
  const response = UrlFetchApp.fetch(embeddingUrl, {
    method: 'post',
    headers: { 'Content-Type': 'application/json' },
    payload: JSON.stringify(payload)
  });
  return JSON.parse(response.getContentText()).embedding.values;
}

/**
 * Hjelpefunksjon for å kalle LLM og få tekst-svar.
 */
function callGemini(prompt) {
  const completionUrl = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=' + GOOGLE_AI_API_KEY;
  const payload = {
      contents: [{
        parts: [{ "text": prompt }]
      }]
  };
  const response = UrlFetchApp.fetch(completionUrl, {
    method: 'post',
    headers: { 'Content-Type': 'application/json' },
    payload: JSON.stringify(payload)
  });
  return JSON.parse(response.getContentText()).candidates[0].content.parts[0].text.trim();
}

/**
 * Hjelpefunksjon for å garantere JSON-svar fra LLM.
 */
function callGeminiForJson(prompt) {
  const completionUrl = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=' + GOOGLE_AI_API_KEY;
  const payload = {
      contents: [{
        parts: [{ "text": prompt }]
      }],
      generation_config: {
        "response_mime_type": "application/json"
      }
  };
  const response = UrlFetchApp.fetch(completionUrl, {
    method: 'post',
    headers: { 'Content-Type': 'application/json' },
    payload: JSON.stringify(payload)
  });
  const responseText = response.getContentText();
  const responseObject = JSON.parse(responseText);
  const jsonStringFromAi = responseObject.candidates[0].content.parts[0].text;
  return JSON.parse(jsonStringFromAi);
}

/**
 * VERKTØY 1: Sjekker DFØs høyrisikoliste.
 */
function dfoRiskCheckTool(produkt) {
  Logger.log(`BRUKER VERKTØY: DFØ Høyrisikosjekk for produktet: "${produkt}"`);
  const kategorier = {
    "IKT-utstyr og elektronikk": ["solcellepaneler", "mobiltelefoner", "datamaskiner"],
    "Tekstiler og klær": ["arbeidstøy", "uniformer"]
  };
  let funnetKategori = null;
  for (const kategori in kategorier) {
    if (kategorier[kategori].includes(produkt.toLowerCase())) {
      funnetKategori = kategori;
      break;
    }
  }
  if (funnetKategori) {
    return `\n--- Resultat fra DFØs Høyrisikoliste ---\nKilde: anskaffelser.no\nSammendrag: Produktet '${produkt}' tilhører kategorien '${funnetKategori}', som er vurdert til å ha HØY RISIKO for brudd på menneskerettigheter.\n`;
  }
  return "\nProduktet ble ikke funnet i DFØs definerte høyrisikokategorier.\n";
}

/**
 * VERKTØY 2: Utfører et generelt Google-søk.
 */
function googleSearchTool(query) {
  Logger.log(`BRUKER VERKTØY: Google-søk med spørring: "${query}"`);
  // Simulert for testformål
  return `\n--- Resultat fra Google-søk ---\nKilde: Eksternt søk\nSammendrag: Fant ingen spesifikk informasjon for '${query}'.\n`;
}

/**
 * OPPDATERT VERKTØY: Sjekker om et FAGOMRÅDE har behov for lærlinger.
 */
function checkApprenticeshipRegistryTool(fagomraade) {
  Logger.log(`BRUKER VERKTØY: Oslofag.no sjekk for fagområdet: "${fagomraade}"`);
  
  // Simulert oppslag mot oslofag.no for fag med særlig behov
  const fagMedBehov = ["tømrerfaget", "rørleggerfaget", "elektrofag", "betongfaget"];
  
  if (fagMedBehov.includes(fagomraade.toLowerCase())) {
    return `\n--- Resultat fra Oslofag.no ----\nKilde: oslofag.no\nResultat: Fagområdet '${fagomraade}' er identifisert som et fag med særlig behov for læreplasser.\n`;
  }
  return `\n--- Resultat fra Oslofag.no ---\nKilde: oslofag.no\nResultat: Fagområdet '${fagomraade}' er ikke på listen over fag med særlig behov for læreplasser.\n`;
}

/**
 * VERKTØY 4: Henter tekst fra en forskrift.
 */
function fetchRegulationTool(navn) {
  Logger.log(`BRUKER VERKTØY: Henter forskrift: "${navn}"`);
  if (navn.toLowerCase().includes("lærlinger")) {
    return `\n--- Resultat fra Lovdata ---\nKilde: Forskrift om offentlige anskaffelser (lovdata.no)\nUtdrag (§ 7-9): Oppdragsgiver skal i alle kontrakter om bygge- og anleggsarbeider og tjenester stille krav om at leverandøren og eventuelle underleverandører har lærlinger. Plikten gjelder for kontrakter med en varighet på over tre måneder og en anslått verdi på over 1,75 millioner kroner ekskl. mva.\n`;
  }
  return "\nForskriften ble ikke funnet.\n";
}

```

### JSON kunnskapsbase for Oslomodell-agent:
```json
[
    {
        "id":"oslo-001",
        "content":"4. Anvendelsesområde for Oslomodellens seriøsitetskrav\n4.1 4.2 4.3 I bygge-, anleggs- og tjenesteanskaffelser fra kr 100 000 til kr 500 000 skal krav A-E\nalltid benyttes. Krav F-T skal benyttes ved risiko for arbeidslivskriminalitet og sosial\ndumping.\nI bygge-, anleggs- og renholdsanskaffelser over kr 500 000 skal krav A-U alltid\nbenyttes. Krav V skal benyttes alltid når vilkårene er oppfylt, jf. punkt 6.\nI tjenesteanskaffelser over kr 500 000 skal krav A-H alltid benyttes. Krav I-T skal\nbenyttes ved risiko for arbeidslivskriminalitet eller sosial dumping. Krav V skal alltid\nbenyttes når vilkårene er oppfylt, jf. punkt 6.\n5. 5.1 Begrensninger i bruk av underleverandører i vertikal kjede\nVed kunngjøring av bygge-, anleggs- og tjenesteanskaffelser gjelder følgende adgang til\nbruk av underleverandører, jf. krav H:\na) I anskaffelser der det foreligger risiko for arbeidslivskriminalitet og sosial\ndumping kan det maksimalt tillates ett ledd underleverandører i vertikal kjede.\nb) I anskaffelser der det foreligger høy risiko for arbeidslivskriminalitet eller sosial\ndumping, kan det nektes bruk av underleverandører dersom det ikke er mulig å\nredusere risikoen med mindre inngripende tiltak.\nc) I anskaffelser der det foreligger lav risiko for arbeidslivskriminalitet og sosial\ndumping, kan det åpnes for to ledd underleverandører i vertikal kjede.\n5.2 d) Dersom det er nødvendig for å sikre tilstrekkelig konkurranse eller effektiv\ngjennomføring av kontrakten, kan det i konkurransen åpnes for bruk av flere ledd\nunderleverandører enn det som fremgår ovenfor. Dette må imidlertid ikke skje i\nstørre utstrekning enn nødvendig eller det som følger av forskrift om offentlige\nanskaffelser.\nI kontraktsperioden kan det åpnes for bruk av flere ledd underleverandører enn det som\nfremgår av kontrakten, dersom det på grunn av uforutsette eller spesielle\nomstendigheter er nødvendig for å få gjennomført kontrakten. Dette må imidlertid ikke\nskje i større utstrekning enn nødvendig eller det som følger av forskrift om offentlige\nanskaffelser.\n6. Krav til bruk av lærlinger\nI anskaffelser over statlig terskelverdi for bruk av lærlinger, med varighet over tre måneder og\ninnenfor utførende fagområder med særlig behov for læreplasser, skal det stilles krav til bruk\nav lærlinger, jf. krav V.",
        "metadata":"{\"tema\": \"Seriøsitetskrav\", \"kilde\": \"Instruks for Oslo kommunes anskaffelser\", \"relevante_krav\": [\"A-E\", \"F-T\", \"A-H\", \"A-U\", \"I-T\", \"V\"]}"
    },
    {
        "id":"oslo-002",
        "content":"7 Oslomodellens krav til aktsomhetsvurderinger for ansvarlig næringsliv\n7.1 I alle anskaffelser skal det foretas en vurdering av risiko for brudd på grunnleggende\nmenneskerettigheter, arbeidstakerrettigheter og internasjonal humanitærrett,\nmiljøødeleggelse eller korrupsjon i leverandørkjeden eller andre forhold som tilsier at\nleverandøren ikke bør benyttes.\n7.2 Oslo kommune skal ikke handle med leverandører hvis aktiviteter kan knyttes til\nalvorlige brudd på grunnleggende menneskerettigheter, arbeidstakerrettigheter eller\ninternasjonal humanitærrett, eller alvorlige miljøødeleggelser eller korrupsjon. Dette\nomfatter også at kommunen ikke skal handle med leverandører som direkte eller\nindirekte medvirker til å opprettholde ulovlig okkupasjon.\n7.3 Kravsett A, Alminnelige krav til aktsomhetsvurderinger for ansvarlig næringsliv\nbenyttes i anskaffelser av varer, tjenester, bygg og anlegg over kr 500 000, der det er\nhøy risiko, jf. punkt 7.1.\n7.4 Kravsett B, Forenklede krav til aktsomhetsvurderinger for ansvarlig næringsliv kan\nbenyttes i anskaffelser av varer, tjenester, bygg og anlegg over kr 500 000, der det er\nhøy risiko, jf. punkt 7.1, istedenfor kravsett A, ved enkeltkjøp av varer, bygge-, anleggs-\nog tjenestekontrakter med en varighet på under 1 år eller når markedsundersøkelse\nviser at færre enn tre potensielle tilbydere kan oppfylle de alminnelige kravene til\naktsomhetsvurderinger for ansvarlig næringsliv (umodent marked).\n7.5 Dersom vilkårene for bruk av kravsett B er oppfylt, skal virksomhetene dokumentere\nvurderingen i kontraktsstrategien eller tilsvarende dokument.\n7.6 Virksomhetene kan benytte strengere kvalifikasjons- eller kontraktskrav enn det som er\npålagt der dette er hensiktsmessig. Kravene som stilles må være forholdsmessige.",
        "metadata":"{\"tema\": \"Aktsomhetsvurderinger\", \"kilde\": \"Instruks for Oslo kommunes anskaffelser\", \"relevante_krav\": [\"Kravsett A\", \"Kravsett B\"]}"
    }
]
```

### Kjørelogg for script:

| 12:20:11 | Merknad | Kjøringen har startet |
|---|---|---|
| 12:20:11 | Informasjon | AGENT STARTER med generelt spørsmål: Hvilke krav gjelder for en bygge- og anleggskontrakt til 1.500.000 kr med 'Entreprenør AS' som leverandør? |
| 12:20:13 | Informasjon | Agentens plan: Undersøker temaene Seriøsitetskrav, Aktsomhetsvurderinger, Lærlinger |
| 12:20:14 | Informasjon | Henter kontekst for tema: Seriøsitetskrav |
| 12:20:14 | Informasjon | Henter kontekst for tema: Aktsomhetsvurderinger |
| 12:20:15 | Informasjon | Henter kontekst for tema: Lærlinger |
| 12:20:15 | Informasjon | All intern kontekst hentet. |
| 12:20:25 | Informasjon | Agenten valgte verktøy: dfo_risk_check med input: stål |
| 12:20:25 | Informasjon | BRUKER VERKTØY: DFØ Høyrisikosjekk for produktet: "stål" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: dfo_risk_check med input: sement |
| 12:20:25 | Informasjon | BRUKER VERKTØY: DFØ Høyrisikosjekk for produktet: "sement" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: dfo_risk_check med input: elektronikk |
| 12:20:25 | Informasjon | BRUKER VERKTØY: DFØ Høyrisikosjekk for produktet: "elektronikk" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: dfo_risk_check med input: tømrerfaget |
| 12:20:25 | Informasjon | BRUKER VERKTØY: DFØ Høyrisikosjekk for produktet: "tømrerfaget" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: dfo_risk_check med input: rørleggerfaget |
| 12:20:25 | Informasjon | BRUKER VERKTØY: DFØ Høyrisikosjekk for produktet: "rørleggerfaget" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: dfo_risk_check med input: elektrofag |
| 12:20:25 | Informasjon | BRUKER VERKTØY: DFØ Høyrisikosjekk for produktet: "elektrofag" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: apprenticeship_check med input: tømrerfaget |
| 12:20:25 | Informasjon | BRUKER VERKTØY: Oslofag.no sjekk for fagområdet: "tømrerfaget" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: apprenticeship_check med input: rørleggerfaget |
| 12:20:25 | Informasjon | BRUKER VERKTØY: Oslofag.no sjekk for fagområdet: "rørleggerfaget" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: apprenticeship_check med input: elektrofag |
| 12:20:25 | Informasjon | BRUKER VERKTØY: Oslofag.no sjekk for fagområdet: "elektrofag" |
| 12:20:25 | Informasjon | Agenten valgte verktøy: regulation_fetch med input: statlig terskelverdi lærlingekrav |
| 12:20:25 | Informasjon | BRUKER VERKTØY: Henter forskrift: "statlig terskelverdi lærlingekrav" |
| 12:20:56 | Informasjon | --- AGENTENS ENDELIGE SVAR --- |
| 12:20:56 | Informasjon | For en bygge- og anleggskontrakt verdt 1.500.000 kr med Entreprenør AS gjelder følgende krav basert på 'Instruks for Oslomodellen' og den tilgjengelige konteksten:<br><br>### 1. Seriøsitetskrav (jf. punkt 4 i Internt Regelverk)<br><br>Da kontraktsverdien (1.500.000 kr) er over 500.000 kr, gjelder følgende:<br>*   **Krav A-U** skal alltid benyttes for bygge- og anleggsanskaffelsen [Internt Regelverk, punkt 4.2]. Disse kravene omfatter en rekke seriøsitetskrav.<br>*   **Krav V** skal benyttes alltid når vilkårene er oppfylt, jf. punkt 6 om lærlinger [Internt Regelverk, punkt 4.2].<br><br>### 2. Begrensninger i bruk av underleverandører (jf. punkt 5 i Internt Regelverk)<br><br>For bygge- og anleggsanskaffelser gjelder følgende for bruk av underleverandører:<br>*   **Vurdering av risiko for arbeidslivskriminalitet og sosial dumping:** Den spesifikke risikoen for denne kontrakten er ikke angitt.<br>    *   Dersom det foreligger **risiko for arbeidslivskriminalitet og sosial dumping**, kan det maksimalt tillates **ett ledd underleverandører** i vertikal kjede [Internt Regelverk, punkt 5.1 a)]. Dette er ofte en standardvurdering i bygge- og anleggsbransjen.<br>    *   Dersom det foreligger **høy risiko for arbeidslivskriminalitet eller sosial dumping**, kan bruk av underleverandører nektes [Internt Regelverk, punkt 5.1 b)].<br>    *   Dersom det foreligger **lav risiko for arbeidslivskriminalitet og sosial dumping**, kan det åpnes for **to ledd underleverandører** i vertikal kjede [Internt Regelverk, punkt 5.1 c)].<br>*   **Fleksibilitet ved behov:** Det kan åpnes for bruk av flere ledd underleverandører dersom det er nødvendig for å sikre tilstrekkelig konkurranse eller effektiv gjennomføring av kontrakten. Dette må imidlertid ikke skje i større utstrekning enn nødvendig eller det som følger av forskrift om offentlige anskaffelser [Internt Regelverk, punkt 5.2 d)]. Dette gjelder også i kontraktsperioden ved uforutsette eller spesielle omstendigheter [Internt Regelverk, punkt 5.2].<br><br>### 3. Krav til bruk av lærlinger (jf. punkt 6 i Internt Regelverk)<br><br>Krav om bruk av lærlinger (Krav V) skal stilles dersom følgende vilkår er oppfylt:<br>*   **Kontraktsverdi:** Anskaffelsen er over statlig terskelverdi for bruk av lærlinger. Kontraktsverdien på 1.500.000 kr er en betydelig sum, og det er sannsynlig at den overstiger terskelverdien (eksakt terskelverdi er ikke oppgitt i konteksten).<br>*   **Varighet:** Kontrakten har en varighet over tre måneder. (Varigheten av denne kontrakten er ikke spesifisert i spørsmålet og må sjekkes).<br>*   **Fagområde:** Anskaffelsen er innenfor utførende fagområder med særlig behov for læreplasser. Bygge- og anleggskontrakter involverer ofte slike fagområder. Ifølge Oslofag.no er **tømrerfaget**, **rørleggerfaget** og **elektrofag** identifisert som fag med særlig behov for læreplasser [oslofag.no].<br><br>Hvis alle disse vilkårene er oppfylt, skal Krav V anvendes [Internt Regelverk, punkt 6].<br><br>### 4. Aktsomhetsvurderinger for ansvarlig næringsliv (jf. punkt 7 i Internt Regelverk)<br><br>*   **Generell vurderingsplikt:** I alle anskaffelser skal det foretas en vurdering av risiko for brudd på grunnleggende menneskerettigheter, arbeidstakerrettigheter og internasjonal humanitærrett, miljøødeleggelse eller korrupsjon i leverandørkjeden [Internt Regelverk, punkt 7.1].<br>*   **Forbud mot å handle med uansvarlige leverandører:** Oslo kommune skal ikke handle med leverandører hvis aktiviteter kan knyttes til alvorlige brudd på ovennevnte prinsipper [Internt Regelverk, punkt 7.2].<br>*   **Anvendelse av kravsett A eller B:** Kontraktsverdien (1.500.000 kr) er over 500.000 kr, noe som potensielt utløser krav om bruk av Kravsett A eller B.<br>    *   **Kravsett A** (Alminnelige krav til aktsomhetsvurderinger) benyttes i anskaffelser over 500.000 kr "der det er høy risiko" jf. punkt 7.1 [Internt Regelverk, punkt 7.3].<br>    *   **Kravsett B** (Forenklede krav til aktsomhetsvurderinger) kan benyttes i stedet for Kravsett A, også over 500.000 kr "der det er høy risiko", og i tillegg ved enkeltkjøp, kontrakter under 1 år, eller der markedet er umodent [Internt Regelverk, punkt 7.4].<br>*   **Risikovurderingens betydning:** Den eksterne konteksten indikerer at "Produktet ble ikke funnet i DFØs definerte høyrisikokategorier" for denne anskaffelsen [DFØ]. Dette betyr at det ikke foreligger en automatisk klassifisering av "høy risiko" for dette produktet basert på DFØs kategorier. Som et resultat er Kravsett A eller B **ikke automatisk påkrevd** basert på denne informasjonen alene. Den innledende risikovurderingen (punkt 7.1) må likevel utføres. Dersom denne konkrete risikovurderingen for den aktuelle bygge- og anleggskontrakten likevel avdekker "høy risiko" for brudd på grunnleggende rettigheter, miljø eller korrupsjon i leverandørkjeden, vil Kravsett A eller B måtte benyttes.<br>*   **Dokumentasjonsplikt for Kravsett B:** Dersom vilkårene for bruk av Kravsett B er oppfylt og det velges, skal virksomheten dokumentere vurderingen i kontraktsstrategien eller tilsvarende dokument [Internt Regelverk, punkt 7.5].<br>*   **Mulighet for strengere krav:** Virksomhetene kan benytte strengere kvalifikasjons- eller kontraktskrav enn det som er pålagt der dette er hensiktsmessig, forutsatt at kravene er forholdsmessige [Internt Regelverk, punkt 7.6].<br><br>### Overordnet vurdering og konkluderende anbefaling<br><br>For denne bygge- og anleggskontrakten på 1.500.000 kr, er det et omfattende sett av krav som gjelder, primært drevet av kontraktstypen og verdien som plasserer den "over kr 500 000" i Oslomodellen. Kravene er designede for å sikre seriøsitet, kontroll med underleverandører, fremme lærlingebruk og adressere ansvarlig næringsliv.<br><br>Den spesifikke mangelen på informasjon om kontraktens varighet er kritisk for lærlingekravet, og mangelen på en klar risikoklassifisering for arbeidslivskriminalitet/sosial dumping krever en forsiktig tilnærming til underleverandørledd. For aktsomhetsvurderinger er det viktig å merke seg at DFØs høyrisikokategorier for produktet ikke gjelder, men at en prosjektspesifikk risikovurdering (jf. punkt 7.1) fortsatt er obligatorisk og kan utløse strengere krav (A eller B).<br><br>**Konkluderende anbefaling for denne spesifikke anskaffelsen:**<br><br>1.  **Pålegg alltid Krav A-U** som seriøsitetskrav.<br>2.  **Gjennomfør en grundig risikovurdering for arbeidslivskriminalitet og sosial dumping.** Basert på typisk risiko i bygg og anlegg, bør man som utgangspunkt legge til grunn "risiko" (ikke "lav risiko") og dermed **begrense til maksimalt ett ledd underleverandører i vertikal kjede**, med mindre en dokumentert vurdering viser lav risiko eller at markedet krever flere ledd iht. punkt 5.2 d).<br>3.  **Avklar kontraktens varighet.** Hvis den er over tre måneder, og involverer fagområder som tømrer, rørlegger eller elektro, **må Krav V om lærlinger stilles.**<br>4.  **Utfør alltid en risikovurdering** i henhold til punkt 7.1 for menneskerettigheter, arbeidstakerrettigheter, miljø og korrupsjon i leverandørkjeden. Selv om "produktet" ikke er i DFØs høyrisikokategorier, kan spesifikke forhold ved denne kontrakten eller Entreprenør AS' kjede likevel tilsi høy risiko. **Dersom denne risikovurderingen avdekker høy risiko, skal Kravsett A eller B benyttes.** Uavhengig av om kravsett A/B pålegges, skal kommunen ikke handle med leverandører som knyttes til alvorlige brudd. |
| 12:20:56 | Merknad | Kjøringen er fullført |

