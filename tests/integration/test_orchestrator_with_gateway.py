# test_orchestrator_with_gateway.py (korrigert og robust versjon)
import asyncio
from tools.rpc_gateway_client import RPCGatewayClient
from models.procurement_models import TriageResult

async def test_client_workflow():
    """
    Tester en komplett, selvstendig arbeidsflyt via RPCGatewayClient.
    """
    print("--- Starter full arbeidsflyt-test med RPCGatewayClient ---")
    
    async with RPCGatewayClient(agent_id="anskaffelsesassistenten") as client:
        
        # --- Steg 1: Opprett en ny anskaffelse for å få en ekte request_id ---
        print("--> Steg 1: Oppretter en ny anskaffelse...")
        try:
            # Forutsetter at du har en 'opprett_anskaffelse' convenience-metode i clienten,
            # eller så kan vi bruke det generiske 'call'.
            opprett_params = {
                "p_navn": "Test fra orchestrator-script",
                "p_verdi": 99000,
                "p_beskrivelse": "En test for å verifisere flyten."
            }
            opprett_resultat = await client.call("database.opprett_anskaffelse", opprett_params)
            print("Opprett resultat:", opprett_resultat)
            
            test_request_id = opprett_resultat['request_id']

        except Exception as e:
            print(f"!!! FEIL i Steg 1: Klarte ikke opprette anskaffelse. {e} !!!")
            return

        # --- Steg 2: Bruk den ekte ID-en til å lagre et triage-resultat ---
        print(f"\n--> Steg 2: Lagrer triage for request_id: {test_request_id}")
        try:
            triage = TriageResult(
                farge="GRØNN",
                begrunnelse="Test begrunnelse fra orchestrator-test",
                confidence=0.98
            )
            triage_resultat = await client.lagre_triage_resultat(test_request_id, triage)
            print("Lagre triage resultat:", triage_resultat)

        except Exception as e:
            print(f"!!! FEIL i Steg 2: Klarte ikke lagre triage. {e} !!!")
            return
            
        # --- Steg 3: Bruk den ekte ID-en til å oppdatere status ---
        print(f"\n--> Steg 3: Setter status for request_id: {test_request_id}")
        try:
            status_resultat = await client.sett_status(test_request_id, "COMPLETED")
            print("Sett status resultat:", status_resultat)
        
        except Exception as e:
            print(f"!!! FEIL i Steg 3: Klarte ikke sette status. {e} !!!")
            return

        print("\n--- ✅ Test Suksess! RPCGatewayClient fungerer i en komplett arbeidsflyt. ---")

if __name__ == "__main__":
    asyncio.run(test_client_workflow())