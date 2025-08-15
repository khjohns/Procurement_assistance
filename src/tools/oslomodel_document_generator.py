# src/tools/oslomodel_document_generator.py
"""
Oslomodell Document Generator - Genererer strukturerte anskaffelsesnotater
basert på Oslomodell-vurderinger ved bruk av rike datamodeller.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Importer de nye datamodellene
from src.models.procurement_models import ProcurementRequest, OslomodellAssessmentResult, Requirement

class OslomodelDocumentGenerator:
    """Genererer markdown-dokumenter for Oslomodell-vurderinger."""
    
    def __init__(self, output_dir: str = "procurement_documents"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_document(self, procurement_data: ProcurementRequest, 
                         oslomodell_result: OslomodellAssessmentResult) -> str:
        """
        Genererer komplett anskaffelsesnotat basert på datamodeller.
        
        Args:
            procurement_data: Objekt med data om anskaffelsen.
            oslomodell_result: Objekt med resultat fra Oslomodell-vurdering.
            
        Returns:
            Filsti til generert dokument.
        """
        timestamp = datetime.now()
        doc_id = f"oslomodell_{procurement_data.id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Generer markdown-innhold
        content = self._generate_markdown_content(
            procurement_data, 
            oslomodell_result,
            timestamp
        )
        
        # Lagre dokument
        filename = f"{doc_id}.md"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(filepath)
    
    def _generate_markdown_content(self, procurement: ProcurementRequest, 
                                  assessment: OslomodellAssessmentResult,
                                  timestamp: datetime) -> str:
        """Genererer markdown-innhold for dokumentet fra datamodeller."""
        
        lines = []
        
        # Header
        lines.extend([
            f"# Anskaffelsesnotat - Oslomodellen",
            f"",
            f"**Generert:** {timestamp.strftime('%d.%m.%Y kl. %H:%M')}",
            f"**Anskaffelses-ID:** {procurement.id}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 1: Anskaffelsesinformasjon
        lines.extend([
            f"## 1. Anskaffelsesinformasjon",
            f"",
            f"**Navn:** {procurement.name}",
            f"**Verdi:** {procurement.value:,} NOK ekskl. mva",
            f"**Kategori:** {procurement.category.value}",
            f"**Varighet:** {procurement.duration_months} måneder",
            f"",
            f"**Beskrivelse:**",
            f"> {procurement.description or 'Ingen beskrivelse oppgitt'}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 2: Risikovurdering
        risk_level = assessment.crime_risk_assessment
        risk_emoji = {"høy": "🔴", "moderat": "🟡", "lav": "🟢"}.get(risk_level.lower(), "⚪")
        
        lines.extend([
            f"## 2. Risikovurdering",
            f"",
            f"**Vurdert risiko for arbeidslivskriminalitet:** {risk_emoji} **{risk_level.upper()}**",
            f"**Risiko for sosial dumping:** {assessment.social_dumping_risk.upper()}",
            f"**Risiko for brudd på menneskerettigheter:** {assessment.dd_risk_assessment.upper()}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 3: Påkrevde seriøsitetskrav
        required_reqs = assessment.required_requirements
        lines.extend([
            f"## 3. Påkrevde seriøsitetskrav",
            f"",
            f"**Antall krav:** {len(required_reqs)} stk",
            f"**Hjemmel:** Instruks for Oslo kommunes anskaffelser, punkt 4",
            f"",
            f"### Kravliste:",
            f""
        ])
        
        for req in sorted(required_reqs, key=lambda r: r.code):
            lines.append(f"- **Krav {req.code}:** {req.name} - *{req.description}*")
        lines.append("")
        
        lines.extend(["---", ""])
        
        # Seksjon 4: Underleverandørbegrensninger
        lines.extend([
            f"## 4. Underleverandørbegrensninger",
            f"",
            f"**Maksimalt antall ledd:** {assessment.subcontractor_levels}",
            f"**Hjemmel:** Instruks punkt 5",
            f"",
            f"### Begrunnelse:",
            f"> {assessment.subcontractor_justification}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 5: Lærlingkrav
        apprentice_req = assessment.apprenticeship_requirement
        lines.extend([
            f"## 5. Lærlingkrav",
            f"",
            f"**Status:** {'Påkrevd' if apprentice_req.required else 'Ikke påkrevd'}",
            f"**Begrunnelse:** {apprentice_req.reason}",
            f"**Minimum antall:** {apprentice_req.minimum_count}",
            f"**Relevante fag:** {', '.join(apprentice_req.applicable_trades) or 'N/A'}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 6: Aktsomhetsvurdering
        dd_requirement = assessment.due_diligence_requirement or 'Ikke påkrevd'
        lines.extend([
            f"## 6. Aktsomhetsvurdering",
            f"",
            f"**Kravsett:** {dd_requirement}",
            f"**Hjemmel:** Instruks punkt 7",
            f""
        ])
        
        if dd_requirement != "Ikke påkrevd":
            lines.extend([
                f"### Krav om aktsomhetsvurdering:",
                f"Leverandør må gjennomføre aktsomhetsvurdering iht. kravsett {dd_requirement}.",
                f""
            ])
        
        lines.extend(["---", ""])
        
        # Seksjon 7: Anbefalinger
        if assessment.recommendations:
            lines.extend([
                f"## 7. Anbefalinger",
                f""
            ])
            for rec in assessment.recommendations:
                lines.append(f"- {rec}")
            lines.extend(["", "---", ""])
        
        # Seksjon 8: Oppfølgingspunkter
        lines.extend([
            f"## 8. Oppfølgingspunkter",
            f"",
            f"### Før kontraktsinngåelse:",
            f"- [ ] Verifiser alle seriøsitetskrav",
            f"- [ ] Gjennomfør prekvalifisering",
            f"- [ ] Kontroller underleverandører",
            f""
        ])
        
        if apprentice_req.required:
            lines.extend([
                f"### Lærlingoppfølging:",
                f"- [ ] Avklar lærlingbehov med leverandør",
                f"- [ ] Etabler oppfølgingsrutiner for lærlinger",
                f""
            ])
        
        lines.extend([
            f"### Under kontraktsperioden:",
            f"- [ ] Månedlig rapportering HMSREG (hvis relevant)",
            f"- [ ] Kvartalsvis kontroll av lønns- og arbeidsvilkår",
            f"- [ ] Stedlige kontroller ved behov",
            f"",
            f"---",
            f"",
            f"## 9. Metadata",
            f"",
            f"**Vurdert av:** {assessment.assessed_by}",
            f"**Vurderingstidspunkt:** {assessment.assessment_date}",
            f"**Konfidens:** {assessment.confidence*100:.0f}%",
            f"**Kilder brukt:** {', '.join(assessment.context_documents_used) or 'Ingen'}",
            f"**Dokumentversjon:** 1.0",
            f"**Status:** UTKAST"
        ])
        
        return "\n".join(lines)
    
    def generate_summary_table(self, assessments: List[OslomodellAssessmentResult]) -> str:
        """Genererer oppsummeringstabell for flere vurderinger."""
        lines = []
        lines.extend([
            "| Anskaffelse | Verdi (NOK) | Risiko | Antall krav | Lærlinger |",
            "|-------------|-------------|--------|--------------|-----------|"
        ])
        
        for assess in assessments:
            name = assess.procurement_name[:30]
            # Antar at verdien må hentes fra et annet sted, da den ikke er i OslomodellAssessmentResult
            # For nå, setter vi den til 0. Dette må justeres.
            value = "N/A" 
            risk = assess.crime_risk_assessment
            req_count = len(assess.required_requirements)
            apprentice = "Ja" if assess.apprenticeship_requirement.required else "Nei"
            
            lines.append(f"| {name} | {value} | {risk} | {req_count} | {apprentice} |")
        
        return "\n".join(lines)
