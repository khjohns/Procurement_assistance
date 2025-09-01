# src/analyzers/company_analyzer.py (Oppdatert med detaljert finansiell uthenting)
"""
En dedikert analysetjeneste som tolker rådata fra Brønnøysundregistrene
og produserer innsikt og risikovurderinger.
"""

from typing import Dict, Any, Optional, List
import structlog
from pydantic import BaseModel, Field

from src.services.brreg_service import ComprehensiveCompanyInfo, BrregCompanyDetails, BrregSignatureInfo

logger = structlog.get_logger()

# --- Pydantic-modeller for analyseresultater (utvidet) ---
class RiskAssessment(BaseModel):
    vurdering: str; begrunnelse: str
class FinancialAnalysis(BaseModel):
    assessment: RiskAssessment; nokkeltall: Dict[str, str] = Field(default_factory=dict)

class CompanyAnalysisResult(BaseModel):
    organisasjonsnummer: str; navn: str
    bankruptcy_risk: RiskAssessment
    financial_strength: FinancialAnalysis
    management_stability: RiskAssessment
    # NY: Et nytt felt for å holde på de detaljerte tallene
    detailed_financials: List[Dict[str, Any]] = Field(default_factory=list)

class CompanyAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.financial_thresholds = config.get("financial_thresholds", {})
        # NY: Mapping fra API-nøkler til brukervennlige navn
        self.key_map = {
            "aarsresultat": "Årsresultat", "totalresultat": "Totalresultat",
            "sumDriftsinntekter": "Sum driftsinntekter", "salgsinntekter": "Salgsinntekter",
            "sumDriftskostnad": "Sum driftskostnad", "loennskostnad": "Lønnskostnad",
            "driftsresultat": "Driftsresultat", "nettoFinans": "Netto finans",
            "sumEiendeler": "Sum eiendeler", "goodwill": "Goodwill",
            "sumAnleggsmidler": "Sum anleggsmidler", "sumOmloepsmidler": "Sum omløpsmidler",
            "sumBankinnskuddOgKontanter": "Bankinnskudd, kontanter o.l.",
            "sumEgenkapitalGjeld": "Sum egenkapital og gjeld", "sumEgenkapital": "Sum egenkapital",
            "sumGjeld": "Sum gjeld", "sumKortsiktigGjeld": "Sum kortsiktig gjeld",
            "sumLangsiktigGjeld": "Sum langsiktig gjeld"
        }

    def analyze(self, company_info: ComprehensiveCompanyInfo) -> Optional[CompanyAnalysisResult]:
        if not company_info.details:
            logger.warning("analyzer.analyze.missing_details"); return None

        orgnr = company_info.details.organisasjonsnummer; navn = company_info.details.navn
        log = logger.bind(orgnr=orgnr, company_name=navn); log.info("analyzer.analyze.start")

        bankruptcy_risk = self._analyze_bankruptcy_risk(company_info.details)
        financial_strength = self._analyze_financial_strength(company_info.financials)
        management_stability = self._analyze_management_stability(company_info.signature)
        # NY: Kall den nye funksjonen for å hente detaljerte tall
        detailed_financials = self._extract_detailed_financials(company_info.financials)

        analysis_result = CompanyAnalysisResult(
            organisasjonsnummer=orgnr, navn=navn,
            bankruptcy_risk=bankruptcy_risk, financial_strength=financial_strength,
            management_stability=management_stability, detailed_financials=detailed_financials
        )
        log.info("analyzer.analyze.success"); return analysis_result

    # ... (_analyze_bankruptcy_risk, _analyze_management_stability, _analyze_financial_strength, _get_score er uendret) ...
    def _analyze_bankruptcy_risk(self, details: BrregCompanyDetails) -> RiskAssessment:
        if details.konkurs: return RiskAssessment(vurdering="KRITISK", begrunnelse="Selskapet er registrert som konkurs.")
        if details.underTvangsavviklingEllerTvangsopplosning: return RiskAssessment(vurdering="HØY", begrunnelse="Selskapet er under tvangsavvikling eller tvangsoppløsning.")
        if details.underAvvikling: return RiskAssessment(vurdering="MIDDELS", begrunnelse="Selskapet er under frivillig avvikling.")
        return RiskAssessment(vurdering="LAV", begrunnelse="Ingen aktive flagg for konkurs, avvikling eller tvangsoppløsning funnet.")

    def _analyze_management_stability(self, signature_info: Optional[BrregSignatureInfo]) -> RiskAssessment:
        if not signature_info or not signature_info.roller: return RiskAssessment(vurdering="UKJENT", begrunnelse="Rolledata er ikke tilgjengelig.")
        board_members = signature_info.roller.get("Styremedlem", []); board_leader = signature_info.roller.get("Styrets leder", []); total_board_size = len(board_members) + len(board_leader)
        if total_board_size >= 3: return RiskAssessment(vurdering="NORMAL", begrunnelse=f"Styret har 3 eller flere medlemmer ({total_board_size} totalt).")
        if total_board_size > 0: return RiskAssessment(vurdering="MINIMAL", begrunnelse=f"Styret har færre enn 3 medlemmer ({total_board_size} totalt).")
        return RiskAssessment(vurdering="MANGLER", begrunnelse="Ingen styremedlemmer er registrert.")

    def _analyze_financial_strength(self, financials: Optional[Dict[str, Any]]) -> FinancialAnalysis:
        if not financials:
            logger.warning("analyzer.financial_analysis.missing_data")
            return FinancialAnalysis(assessment=RiskAssessment(vurdering="UKJENT", begrunnelse="Regnskapsdata for siste år er ikke tilgjengelig."), nokkeltall={})
        try:
            egenkapital = financials.get("egenkapitalGjeld", {}).get("egenkapital", {}).get("sumEgenkapital", 0)
            eiendeler = financials.get("eiendeler", {}).get("sumEiendeler", 0)
            omloepsmidler = financials.get("eiendeler", {}).get("omloepsmidler", {}).get("sumOmloepsmidler", 0)
            kortsiktig_gjeld = financials.get("egenkapitalGjeld", {}).get("gjeldOversikt", {}).get("kortsiktigGjeld", {}).get("sumKortsiktigGjeld", 0)
            driftsresultat = financials.get("resultatregnskapResultat", {}).get("driftsresultat", {}).get("driftsresultat", 0)
            driftsinntekter = financials.get("resultatregnskapResultat", {}).get("driftsresultat", {}).get("driftsinntekter", {}).get("sumDriftsinntekter", 0)
            soliditet = (egenkapital / eiendeler * 100) if eiendeler else 0
            likviditetsgrad = (omloepsmidler / kortsiktig_gjeld) if kortsiktig_gjeld else 0
            resultatgrad = (driftsresultat / driftsinntekter * 100) if driftsinntekter else 0
            soliditet_score = self._get_score(soliditet, self.financial_thresholds.get('soliditet_prosent', {}))
            likviditet_score = self._get_score(likviditetsgrad, self.financial_thresholds.get('likviditetsgrad', {}))
            resultatgrad_score = self._get_score(resultatgrad, self.financial_thresholds.get('resultatgrad_prosent', {}))
            score_map = {"KRITISK": 0, "SVAK": 1, "TILFREDSSTILLENDE": 2, "GOD": 3, "MEGET GOD": 4}
            final_assessment_str = min([soliditet_score, likviditet_score, resultatgrad_score], key=lambda x: score_map.get(x, 0))
            begrunnelse = f"Samlet vurdering basert på Soliditet: {soliditet_score}, Likviditet: {likviditet_score}, og Resultatgrad: {resultatgrad_score}."
            return FinancialAnalysis(assessment=RiskAssessment(vurdering=final_assessment_str, begrunnelse=begrunnelse), nokkeltall={"Soliditet": f"{soliditet:.1f}%", "Likviditetsgrad": f"{likviditetsgrad:.2f}", "Resultatgrad": f"{resultatgrad:.1f}%"})
        except Exception as e:
            logger.error("analyzer.financial_analysis.failed", error=str(e), exc_info=True)
            return FinancialAnalysis(assessment=RiskAssessment(vurdering="FEIL", begrunnelse=f"En feil oppstod under finansiell analyse: {e}"), nokkeltall={})

    def _get_score(self, value: float, tiers: Dict[str, float]) -> str:
        if value < tiers.get('kritisk', float('-inf')): return "KRITISK"
        if value < tiers.get('svak', float('-inf')): return "SVAK"
        if value < tiers.get('tilfredsstillende', float('-inf')): return "TILFREDSSTILLENDE"
        if value < tiers.get('god', float('-inf')): return "GOD"
        return "MEGET GOD"

    def _extract_detailed_financials(self, financials: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        NY: Går rekursivt gjennom regnskapsdata og trekker ut alle tall
        som er definert i key_map.
        """
        if not financials:
            return []

        extracted_data = []
        
        def recurse_extract(data_node: Any):
            if isinstance(data_node, dict):
                for key, value in data_node.items():
                    if key in self.key_map and isinstance(value, (int, float)):
                        extracted_data.append({"label": self.key_map[key], "value": value})
                    elif isinstance(value, dict):
                        recurse_extract(value)
        
        recurse_extract(financials)
        return extracted_data