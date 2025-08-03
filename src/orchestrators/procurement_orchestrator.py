# orchestrators/procurement_orchestrator.py
import structlog
from src.models.procurement_models import AnskaffelseRequest
from src.specialists.triage_agent import TriageAgent
from src.specialists.protocol_generator import ProtocolGenerator
from src.tools.rpc_gateway_client import RPCGatewayClient

logger = structlog.get_logger()

class ProcurementOrchestrator:
    def __init__(self, triage_agent: TriageAgent, protocol_generator: ProtocolGenerator):
        self.triage_agent = triage_agent
        self.protocol_generator = protocol_generator
        logger.info("ProcurementOrchestrator initialized")

    async def kjor_prosess(self, request: AnskaffelseRequest):
        # Bruk den ID-en som ble generert da request-objektet ble laget
        request_id_str = str(request.id)

        async with RPCGatewayClient(agent_id="anskaffelsesassistenten") as gateway:
            logger.info("Starting procurement process", request_id=request_id_str)
            
            try:
                # === STEG 0: OPPRETT SELVE SAKEN I DATABASEN ===
                # Dette er det manglende, kritiske steget.
                logger.info("Creating procurement request in database...", request_id=request_id_str)
                opprett_params = {
                    "p_id": request_id_str, # Vi sender med ID-en
                    "p_navn": request.navn,
                    "p_verdi": request.verdi,
                    "p_beskrivelse": request.beskrivelse
                }
                # Bruk en ny RPC-funksjon for å opprette med en gitt ID
                await gateway.call("database.opprett_anskaffelse_med_id", opprett_params)
                logger.info("Procurement request created successfully in database", request_id=request_id_str)

                # --- Nå fortsetter resten av flyten som før ---

                # Steg 1: Kjør triagering
                triage_result = await self.triage_agent.vurder_anskaffelse(request)
                logger.info("Triage completed", request_id=request_id_str, result=triage_result.farge)

                # Steg 2: Lagre triageringsresultat via RPC
                await gateway.lagre_triage_resultat(request_id_str, triage_result)
                logger.info("Triage result saved to database", request_id=request_id_str)
                

                # Steg 3: Vurder neste steg basert på triage og konfidens
                pause_for_review = False
                if triage_result.farge == "RØD":
                    logger.warning("Triage result is RED, flagging for manual review.", 
                                 request_id=request.id)
                    pause_for_review = True
                elif triage_result.confidence < 0.85:
                    logger.warning("Confidence score is below threshold (0.85), flagging for manual review.", 
                                   request_id=request.id, 
                                   confidence=triage_result.confidence)
                    pause_for_review = True

                if pause_for_review:
                    status_response = await gateway.sett_status(request.id, "PAUSED_FOR_REVIEW")
                    logger.info("Process halted for manual review.", 
                               request_id=request.id,
                               status_response=status_response)
                    return triage_result

                # Hvis vi kommer hit, er det GRØNN/GUL med høy nok konfidens
                logger.info("Triage result is GREEN or YELLOW with high confidence, proceeding to protocol generation.", 
                            request_id=request.id, 
                            farge=triage_result.farge)
                
                # Steg 4: Generer protokoll
                protocol_result = await self.protocol_generator.generate_protocol(request)
                logger.info("Protocol generated", 
                            request_id=request.id, 
                            confidence=protocol_result.confidence)
                
                # Steg 5: Lagre protokoll via RPC
                protokoll_response = await gateway.lagre_protokoll(
                    request.id,
                    protocol_result.protocol_text,
                    protocol_result.confidence
                )
                logger.info("Protocol saved to database",
                           request_id=request.id,
                           response=protokoll_response)
                
                # Steg 6: Oppdater status
                await gateway.sett_status(request.id, "PROTOCOL_GENERATED")

                return protocol_result
                
            except Exception as e:
                logger.error("Error in procurement process", request_id=request_id_str, error=str(e), exc_info=True)
                try:
                    await gateway.sett_status(request_id_str, "ERROR")
                except Exception as final_e:
                    logger.error("Failed to set final ERROR status", request_id=request_id_str, final_error=str(final_e))
                raise
