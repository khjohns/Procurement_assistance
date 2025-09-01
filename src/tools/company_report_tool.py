# src/tools/company_report_tool.py (Oppdatert med vedlegg-seksjon)
"""
Et komplett verktøy som bruker BrregService og CompanyAnalyzer til å generere
en omfattende selskapsrapport, inkludert risiko, finans og signaturrett.
"""

import structlog
from src.services.brreg_service import BrregService, ComprehensiveCompanyInfo
from src.analyzers.company_analyzer import CompanyAnalyzer, CompanyAnalysisResult

logger = structlog.get_logger()

class CompanyReportTool:
    def __init__(self, brreg_service: BrregService, analyzer: CompanyAnalyzer):
        self.brreg_service = brreg_service
        self.analyzer = analyzer

    async def generate_report(self, orgnr: str, official_name: str) -> str:
        # ... (uendret)
        log = logger.bind(orgnr=orgnr, company_name=official_name); log.info("report_tool.generate_report.start")
        comprehensive_data = await self.brreg_service.get_comprehensive_company_info(orgnr)
        analysis_result = self.analyzer.analyze(comprehensive_data)
        if not analysis_result:
            log.error("report_tool.generate_report.analysis_failed"); return f"**FEIL:** Kunne ikke generere analyse for '{official_name}' ({orgnr})."
        report = self._format_report(analysis_result, comprehensive_data); log.info("report_tool.generate_report.success"); return report

    def _format_report(self, analysis: CompanyAnalysisResult, data: ComprehensiveCompanyInfo) -> str:
        parts = [f"### Selskapsrapport for '{analysis.navn}' ({analysis.organisasjonsnummer})"]
        
        # --- SEKSJON 1, 2, 3, 4 (uendret) ---
        parts.append("\n---"); parts.append("#### **1. Risiko og Nøkkelstatus**")
        risk = analysis.bankruptcy_risk; parts.append(f"- **Konkursrisiko:** {risk.vurdering}"); parts.append(f"  - *Begrunnelse:* {risk.begrunnelse}")
        stability = analysis.management_stability; parts.append(f"- **Styrets Stabilitet:** {stability.vurdering}"); parts.append(f"  - *Begrunnelse:* {stability.begrunnelse}")
        if data.details and data.details.antallAnsatte is not None: parts.append(f"- **Antall ansatte:** {data.details.antallAnsatte}")
        parts.append("\n---"); parts.append("#### **2. Signaturrett og Roller**")
        if data.signature:
            if data.signature.signatur: parts.append("\n**Signaturrett:**"); parts.append(f"> {data.signature.signatur.beskrivelse}")
            else: parts.append("\n**Signaturrett:**\n> *Ingen spesifikk signaturregel er registrert.*")
            if data.signature.prokura: parts.append("\n**Prokura:**"); parts.append(f"> {data.signature.prokura.beskrivelse}")
            if data.signature.roller:
                parts.append("\n**Registrerte Nøkkelpersoner:**")
                role_order = ["Daglig leder", "Styrets leder", "Nestleder", "Styremedlem", "Varamedlem", "Innehaver av prokura"]
                sorted_roles = sorted(data.signature.roller.keys(), key=lambda x: role_order.index(x) if x in role_order else len(role_order))
                for role_type in sorted_roles: parts.append(f"- **{role_type}:** {', '.join(data.signature.roller[role_type])}")
            else: parts.append("\n- *Ingen nøkkelpersoner er registrert.*")
        else: parts.append("\n*Kunne ikke hente informasjon om roller og signaturrett.*")
        parts.append("\n---"); parts.append("#### **3. Finansiell Analyse (Siste Tilgjengelige Regnskapsår)**")
        fin_analysis = analysis.financial_strength; parts.append(f"- **Samlet Vurdering:** {fin_analysis.assessment.vurdering}"); parts.append(f"  - *Begrunnelse:* {fin_analysis.assessment.begrunnelse}")
        if fin_analysis.nokkeltall:
            parts.append("\n**Beregnede Nøkkeltall:**")
            for key, value in fin_analysis.nokkeltall.items(): parts.append(f"- **{key}:** {value}")
        if data.financials:
            arsresultat = data.financials.get("resultatregnskapResultat", {}).get("aarsresultat")
            if arsresultat is not None: parts.append(f"- **Årsresultat:** {arsresultat:,.0f} NOK".replace(",", " "))
        
        # --- NY SEKSJON 5: DETALJERT REGNSKAP ---
        if analysis.detailed_financials:
            parts.append("\n---")
            parts.append("#### **5. Detaljer fra Regnskap (Vedlegg)**")
            # Sorter for konsistent visning
            sorted_financials = sorted(analysis.detailed_financials, key=lambda x: x['label'])
            for item in sorted_financials:
                # Formater tallet på en lesbar måte
                formatted_value = f"{item['value']:,.0f} NOK".replace(",", " ")
                parts.append(f"- **{item['label']}:** {formatted_value}")

        # --- SEKSJON 6 (tidligere 4): BEGRENSNINGER ---
        parts.append("\n---")
        parts.append("#### **6. Datagrunnlag og Begrensninger**")
        parts.append("> *Rapporten er generert basert på offentlig tilgjengelige data fra Brønnøysundregistrenes åpne API-er...")

        return "\n".join(parts)