# test_gateway.py (endelig versjon)
import asyncio
import httpx
import uuid

GATEWAY_URL = "http://localhost:8000/rpc"
AGENT_ID = "anskaffelsesassistenten"


async def call_rpc(client: httpx.AsyncClient, method: str, params: dict, agent_id: str = AGENT_ID) -> dict:
    """En hjelpefunksjon for å gjøre RPC-kall."""
    rpc_request = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    
    response = await client.post(
        GATEWAY_URL,
        json=rpc_request,
        headers={"X-Agent-ID": agent_id}
    )
    return response.json()


async def run_procurement_workflow_test():
    """Kjører en komplett test av arbeidsflyten."""
    async with httpx.AsyncClient(timeout=30) as client:
        print("--- Starter test av RPC Gateway ---")
        
        # --- Steg 1: Opprett en ny anskaffelsessak ---
        print("--> Steg 1: Oppretter en ny anskaffelsessak...")
        opprett_params = {
            "p_navn": "Endelig Vellykket Test " + str(uuid.uuid4())[:8],
            "p_verdi": 750000,
            "p_beskrivelse": "Dette er en ende-til-ende test som nå vil lykkes."
        }
        opprett_res = await call_rpc(client, "database.opprett_anskaffelse", opprett_params)
        
        # KORREKSJON: Sjekker om 'error' har en verdi, ikke bare om nøkkelen finnes.
        if opprett_res.get("error") is not None:
            print(f"!!! Testen feilet i steg 1: {opprett_res['error']} !!!")
            return
            
        print(f"Respons: {opprett_res}\n")

        request_id = opprett_res.get("result", {}).get("request_id")
        if not request_id:
            print("!!! Kritisk feil: Fikk ikke request_id. Avslutter. !!!")
            return

        # --- Steg 2: Oppdater status ---
        print(f"--> Steg 2: Oppdaterer status for sak {request_id}...")
        status_params = {"p_request_id": request_id, "p_status": "TRIAGE_COMPLETE"}
        status_res = await call_rpc(client, "database.sett_status", status_params)
        
        if status_res.get("error") is not None:
            print(f"--- ❌ Test Feilet i steg 2! Mottok feil: {status_res['error']} ---")
            return
            
        print(f"Respons: {status_res}")
        print("\n--- ✅ Test Suksess! Hele arbeidsflyten fungerer som forventet. ---")


if __name__ == "__main__":
    asyncio.run(run_procurement_workflow_test())