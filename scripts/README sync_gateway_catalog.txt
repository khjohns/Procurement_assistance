Hovedformålet er å sørge for at gateway_service_catalog- og gateway_acl_config-tabellene i
databasen er et nøyaktig speilbilde av verktøyene som er tilgjengelige i Python-koden. Dette
gjør at systemet dynamisk kan oppdage og administrere tilgang til verktøy uten manuelle
databaseendringer.

Nøkkelkomponenter

1. Importer og Registering:
   * Skriptet importerer TOOL_REGISTRY fra src.agent_library.registry. Dette registeret er en
     sentral Python-ordbok som holder styr på alle verktøy som er dekorert med @register_tool.
   * Det importerer deretter agent-moduler som src.specialists.triage_agent og
     src.specialists.oslomodell_agent. Dette er et viktig triks: Bare ved å importere disse
     filene, kjøres @register_tool-dekoratorene i dem, som automatisk fyller TOOL_REGISTRY med
     verktøyinformasjon.

2. `sync_gateway_catalog()`-funksjonen:
   * Kobler til databasen: Den leser DATABASE_URL fra .env-filen og kobler seg til
     PostgreSQL-databasen ved hjelp av asyncpg-biblioteket (en asynkron driver).
   * Genererer SQL: Den kaller to hjelpefunksjoner fra registry-modulen:
       * generate_gateway_catalog_sql(): Denne funksjonen går gjennom TOOL_REGISTRY og
         genererer INSERT ... ON CONFLICT DO UPDATE-SQL-setninger for å legge til eller
         oppdatere verktøy i gateway_service_catalog-tabellen.
       * generate_acl_config_sql(): Denne genererer tilsvarende SQL for å sette opp
         tilgangskontroll (ACL) i gateway_acl_config-tabellen, basert på
         allowed_agents-parameteren i @register_tool.
   * Kjører SQL i en transaksjon: Den kjører de genererte SQL-setningene inne i en
     databasetransaksjon (async with conn.transaction():). Dette sikrer at enten alle
     endringene blir lagret, eller ingen av dem, noe som forhindrer en delvis oppdatert (og
     potensielt ødelagt) tilstand.
   * Logger resultatet: Den logger suksess eller feil og skriver ut en liste over de
     registrerte verktøyene for manuell verifisering.

3. `verify_sync()`-funksjonen:
   * Etter at synkroniseringen er fullført, kjører denne funksjonen SELECT-spørringer mot
     databasen for å hente ut de nylig synkroniserte dataene.
   * Den skriver ut en liste over aktive verktøy fra gateway_service_catalog og tillatelsene
     for reasoning_orchestrator fra gateway_acl_config. Dette gir en umiddelbar bekreftelse på
     at synkroniseringen fungerte som forventet.

4. `main()`-funksjonen:
   * Dette er hovedinngangspunktet som orkestrerer hele prosessen.
   * Den kaller først sync_gateway_catalog() for å utføre synkroniseringen.
   * Hvis synkroniseringen er vellykket, kaller den verify_sync() for å bekrefte.
   * Hvis noe feiler, skriver den en feilmelding og avslutter med en feilkode (sys.exit(1)),
     noe som er nyttig i automatiserte deployerings-pipelines.

Hvordan det brukes

Dette skriptet kjøres vanligvis som en del av en deployeringsprosess. Hver gang en utvikler
legger til et nytt verktøy med @register_tool i en agent, vil kjøring av dette skriptet
automatisk:
1. Oppdage det nye verktøyet.
2. Legge det til i gateway_service_catalog.
3. Sette opp de riktige tilgangsrettighetene i gateway_acl_config.

Dette fjerner behovet for manuelle SQL-oppdateringer, reduserer risikoen for feil og gjør
systemet mer vedlikeholdbart og skalerbart.