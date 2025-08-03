# Notat: Erfaringer fra Implementering av MCP Gateway

**Dato:** 2025-07-31

## 1. Innledning

Dette dokumentet oppsummerer erfaringene og de tekniske valgene som ble gjort under forsøket på å bygge en sentralisert MCP (Model Context Protocol) Gateway. Målet var å skape et robust mellomledd for ruting og autorisasjon av kall fra AI-agenter til ulike verktøy (MCP-tjenester).

## 2. Den Opprinnelige Planen: Bruk av `fastmcp`

Den initielle strategien var å benytte `fastmcp`-biblioteket. Dette ble ansett som den beste tilnærmingen, da det lovet en rask og protokoll-kompatibel måte å bygge en MCP-server på, integrert med FastAPI.

Vi utforsket systematisk flere arkitektoniske mønstre basert på tilgjengelig dokumentasjon og beste praksis:

1.  **Kombinert App (Montering):** Forsøket på å montere `fastmcp`-appen på en sub-path (`/mcp`) i en standard FastAPI-app feilet konsekvent. Til tross for å følge dokumentasjonen nøye (spesielt med tanke på `lifespan`-håndtering), resulterte alle kall til det monterte endepunktet i `404 Not Found`-feil eller tomme svar. Feilsøking viste at `fastmcp` ikke ser ut til å håndtere å bli kjørt på en sub-path på en forutsigbar måte.

2.  **Ren `fastmcp`-server:** For å isolere problemet, forsøkte vi å kjøre en minimal `fastmcp`-applikasjon helt alene, uten FastAPI-montering. Også dette feilet, og serveren klarte ikke engang å starte eller respondere på de mest grunnleggende MCP-kallene som `tools/list`.

3.  **Systematisk Feilsøking:** Vi verifiserte at vi brukte den nyeste versjonen av `fastmcp` og at det ikke var noen åpenbare versjonskonflikter. Vi la også til logging-middleware for å inspisere innkommende requests, men kom til kort da vi ikke kunne integrere middleware på en pålitelig måte med `fastmcp`.

## 3. Konklusjon og Strategiendring

Etter gjentatte og systematiske forsøk, ble det klart at `fastmcp` i sitt nåværende stadium var for ustabilt eller for rigid for vårt bruk. Bibliotekets "magi" og mangel på transparens gjorde det umulig å feilsøke effektivt. Vi brukte uforholdsmessig mye tid på å feilsøke selve rammeverket i stedet for å bygge vår egen logikk.

**Beslutningen ble derfor å forlate `fastmcp` og gå tilbake til en mer fundamental og kontrollerbar tilnærming.**

## 4. Den Endelige Løsningen: Manuell FastAPI Gateway

Den vellykkede løsningen var å bygge gatewayen manuelt med ren FastAPI:

*   **Arkitektur:** En enkel FastAPI-applikasjon med to primære endepunkter:
    *   `GET /health`: For enkel helsesjekk.
    *   `POST /rpc`: Et enkelt endepunkt som tar imot alle JSON-RPC-forespørsler.
*   **Kontroll:** All logikk for parsing av JSON-RPC, ruting basert på `method`-feltet, og håndtering av autorisasjon (ACL) vil bli implementert manuelt inne i `/rpc`-endepunktet. 
*   **Resultat:** Denne tilnærmingen fungerte umiddelbart. Serveren startet pålitelig, og vi fikk full kontroll over request-response-flyten, noe som gjorde videre utvikling og feilsøking trivielt.

## 5. Lærdommer

1.  **Pragmatisme over "korrekthet":** Selv om et spesialisert bibliotek *i teorien* er den "korrekte" løsningen, er det i praksis verdiløst hvis det ikke fungerer pålitelig. En enklere, manuell løsning som gir full kontroll er å foretrekke fremfor en kompleks "svart boks" som feiler.
2.  **Systematisk feilsøking er avgjørende:** Ved å metodisk teste ulike hypoteser (montering, ren server, versjon, logging) kunne vi med sikkerhet konkludere at problemet lå i biblioteket, ikke i vår implementering.
3.  **Verdien av enkle test-caser:** Å ha en enkel `curl`-kommando og en Python-testklient var avgjørende for raskt å verifisere om en endring var vellykket eller ikke.
