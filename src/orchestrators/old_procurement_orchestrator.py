import structlog
from models.procurement_models import AnskaffelseRequest, TriageResult
from specialists.triage_agent import TriageAgent
from tools.supabase_gateway import SupabaseGateway, SupabaseGatewayManager # Import SupabaseGatewayManager
from tools.gemini_gateway import GeminiGateway

logger = structlog.get_logger()

class ProcurementOrchestrator:
    """
    Orkestrerer anskaffelsesprosessen ved å bruke spesialister og verktøy.
    """
    def __init__(self, supabase_access_token: str, project_ref: str, gemini_api_key: str): # Oppdater parametere
        self.gemini_gateway = GeminiGateway(gemini_api_key)
        self.triage_agent = TriageAgent(self.gemini_gateway)
        # Bruk SupabaseGatewayManager for å håndtere tilkobling
        self.db_gateway_manager = SupabaseGatewayManager(supabase_access_token, project_ref)
        self.db_gateway = None # Vil bli satt i kjor_prosess
        logger.info("ProcurementOrchestrator initialized")

    async def kjor_prosess(self, request: AnskaffelseRequest) -> TriageResult:
        logger.info("Starting PoC flow for procurement", request_name=request.navn)
        
        async with self.db_gateway_manager as gateway: # Bruk context manager
            self.db_gateway = gateway # Sett gateway-objektet
            
            # 1. Kall på spesialist-agent
            triage_resultat = await self.triage_agent.vurder_anskaffelse(request)
            
            # 2. Kall på verktøy for å lagre
            await self.db_gateway.lagre_resultat(request_id=request.navn, triage_result=triage_resultat)
            
            logger.info("PoC flow completed", request_name=request.navn)
            return triage_resultat
