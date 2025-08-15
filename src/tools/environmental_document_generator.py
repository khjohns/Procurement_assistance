# src/tools/environmental_document_generator.py
"""
Environmental Document Generator - Genererer strukturerte notater for miljøkravvurderinger.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

class EnvironmentalDocumentGenerator:
    """Genererer markdown-dokumenter for miljøkravvurderinger."""
    
    def __init__(self, output_dir: str = "procurement_documents"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_document(self, procurement_data: Dict[str, Any], 
                         environmental_result: Dict[str, Any]) -> str:
        """
        Genererer miljøkrav-notat.
        
        Args:
            procurement_data: Data om anskaffelsen
            environmental_result: Resultat fra miljøkravvurdering
            
        Returns:
            Filsti til generert dokument
        """
        timestamp = datetime.now()
        doc_id = f"environmental_{procurement_data.get('id', 'unknown')}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Generer markdown-innhold
        content = self._generate_markdown_content(
            procurement_data, 
            environmental_result,
            timestamp
        )
        
        # Lagre dokument
        filename = f"{doc_id}.md"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(filepath)
    
    def _generate_markdown_content(self, procurement: Dict[str, Any], 
                                  assessment: Dict[str, Any],
                                  timestamp: datetime) -> str:
        """Genererer markdown-innhold for miljøkrav-dokumentet."""
        
        lines = []
        
        # Header
        lines.extend([
            f"# Miljøkravvurdering",
            f"",
            f"**Generert:** {timestamp.strftime('%d.%m.%Y kl. %H:%M')}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 1: Anskaffelsesinformasjon
        lines.extend([
            f"## 1. Anskaffelsesinformasjon",
            f"",
            f"**Navn:** {procurement.get('name', 'Ikke oppgitt')}",
            f"**Verdi:** {procurement.get('value', 0):,} NOK ekskl. mva",
            f"**Kategori:** {procurement.get('category', 'Ikke spesifisert')}",
            f"**Varighet:** {procurement.get('duration_months', 0)} måneder",
            f"",
            f"**Beskrivelse:**",
            f"> {procurement.get('description', 'Ingen beskrivelse oppgitt')}",
            f""
        ])
        
        # Spesifikk info for bygge/anlegg
        if procurement.get('includes_construction'):
            lines.extend([
                f"",
                f"### Bygge-/anleggsinformasjon:",
                f"- Byggeplassstørrelse: {procurement.get('construction_site_size', 'Ikke oppgitt')} m²",
                f"- Inkluderer riving: {'Ja' if procurement.get('involves_demolition') else 'Nei'}",
                f"- Inkluderer grunnarbeid: {'Ja' if procurement.get('involves_earthworks') else 'Nei'}",
            ])
        
        # Transport-info
        if procurement.get('involves_transport'):
            lines.extend([
                f"",
                f"### Transportinformasjon:",
                f"- Transporttype: {procurement.get('transport_type', 'Ikke spesifisert')}",
                f"- Estimert volum: {procurement.get('estimated_transport_volume', 'Ikke oppgitt')} tonn/turer",
            ])
        
        lines.extend(["", "---", ""])
        
        # Seksjon 2: Miljørisikovurdering
        risk_level = assessment.get('environmental_risk_level', 'ukjent')
        risk_emoji = {"høy": "🔴", "middels": "🟡", "lav": "🟢"}.get(risk_level.lower(), "⚪")
        
        lines.extend([
            f"## 2. Miljørisikovurdering",
            f"",
            f"**Risikonivå:** {risk_emoji} **{risk_level.upper()}**",
            f"",
            f"### Begrunnelse:",
            f"> {assessment.get('reasoning', 'Ingen begrunnelse oppgitt')}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 3: Standard miljøkrav
        standard_req = assessment.get('standard_miljokrav_applies', False)
        lines.extend([
            f"## 3. Standard klima- og miljøkrav",
            f"",
            f"**Gjelder:** {'✅ JA' if standard_req else '❌ NEI'}",
            f"**Hjemmel:** Instruks om bruk av klima- og miljøkrav",
            f""
        ])
        
        if standard_req:
            lines.extend([
                f"Standard klima- og miljøkrav skal benyttes for denne anskaffelsen.",
                f"Se mal for konkurransegrunnlag for detaljerte krav.",
                f""
            ])
        
        lines.extend(["---", ""])
        
        # Seksjon 4: Transportkrav
        transport_reqs = assessment.get('transport_requirements', [])
        if transport_reqs:
            lines.extend([
                f"## 4. Transportkrav",
                f""
            ])
            
            for req in transport_reqs:
                req_type = req.get('requirement_type', 'Ukjent')
                vehicle_class = req.get('vehicle_class', 'Alle')
                deadline = req.get('deadline_date', 'Ikke spesifisert')
                mandatory = req.get('is_mandatory', False)
                
                lines.extend([
                    f"### {req_type}",
                    f"- Kjøretøyklasse: {vehicle_class}",
                    f"- Frist: {deadline}",
                    f"- Status: {'Obligatorisk' if mandatory else 'Premiering'}",
                    f"- Begrunnelse: {req.get('rationale', 'Ikke oppgitt')}",
                    f""
                ])
            
            lines.extend(["---", ""])
        
        # Seksjon 5: Tilleggskrav
        additional = assessment.get('additional_requirements', [])
        if additional:
            lines.extend([
                f"## 5. Tilleggskrav",
                f""
            ])
            for req in additional:
                lines.append(f"- {req}")
            lines.extend(["", "---", ""])
        
        # Seksjon 6: Unntak
        exceptions = assessment.get('exceptions', [])
        if exceptions:
            lines.extend([
                f"## 6. Unntak fra standard krav",
                f""
            ])
            for exc in exceptions:
                lines.extend([
                    f"### {exc.get('requirement_code', 'Ukjent krav')}",
                    f"- Årsak: {exc.get('reason', 'Ikke oppgitt')}",
                    f"- Godkjent av: {exc.get('approved_by', 'Ikke spesifisert')}",
                    f"- Dato: {exc.get('approval_date', 'Ikke oppgitt')}",
                    f""
                ])
            lines.extend(["---", ""])
        
        # Seksjon 7: Oppfølgingspunkter
        lines.extend([
            f"## 7. Oppfølgingspunkter",
            f"",
            f"### Før konkurranse:",
            f"- [ ] Gjennomfør markedsdialog om miljøkrav",
            f"- [ ] Kartlegg tilgjengelige løsninger",
            f"- [ ] Vurder behov for innovasjonspartnerskap",
            f""
        ])
        
        if transport_reqs:
            lines.extend([
                f"### Transportoppfølging:",
                f"- [ ] Spesifiser transportbehov i konkurransegrunnlag",
                f"- [ ] Etabler rapporteringsrutiner for utslipp",
                f"- [ ] Planlegg kontrollmekanismer",
                f""
            ])
        
        lines.extend([
            f"### Under kontraktsperioden:",
            f"- [ ] Månedlig miljørapportering",
            f"- [ ] Kvartalsvis utslippsrapportering",
            f"- [ ] Årlig miljørevisjon",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 8: Anbefalinger
        recommendations = assessment.get('recommendations', [])
        if recommendations:
            lines.extend([
                f"## 8. Anbefalinger",
                f""
            ])
            for rec in recommendations:
                lines.append(f"- {rec}")
            lines.extend(["", "---", ""])
        
        # Seksjon 9: Dokumentasjonskrav
        lines.extend([
            f"## 9. Dokumentasjonskrav",
            f"",
            f"Leverandør må dokumentere følgende:",
            f"- [ ] Miljøsertifisering (ISO 14001 eller tilsvarende)",
            f"- [ ] Utslippsdata for kjøretøy og maskiner",
            f"- [ ] Avfallshåndteringsplan",
            f"- [ ] Materialoversikt med miljømerking",
            f"- [ ] Plan for utslippsreduksjon",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 10: Metadata
        lines.extend([
            f"## 10. Metadata",
            f"",
            f"**Konfidens:** {assessment.get('confidence', 0)*100:.0f}%",
            f"**Kilder brukt:** {', '.join(assessment.get('sources_used', ['Ingen']))}",
            f"**Vurdert av:** {assessment.get('assessed_by', 'environmental_agent')}",
            f"**Dokumentversjon:** 1.0",
            f"**Status:** UTKAST"
        ])
        
        return "\n".join(lines)
    
    def generate_summary_table(self, assessments: List[Dict[str, Any]]) -> str:
        """Genererer oppsummeringstabell for flere miljøvurderinger."""
        lines = []
        lines.extend([
            "| Anskaffelse | Verdi (NOK) | Miljørisiko | Standard krav | Transport |",
            "|-------------|-------------|-------------|---------------|-----------|"
        ])
        
        for a in assessments:
            proc = a.get('procurement', {})
            env = a.get('environmental', {})
            
            name = proc.get('name', 'Ukjent')[:30]
            value = f"{proc.get('value', 0):,}"
            risk = env.get('environmental_risk_level', 'ukjent')
            std_req = "Ja" if env.get('standard_miljokrav_applies') else "Nei"
            transport = "Ja" if env.get('transport_requirements') else "Nei"
            
            lines.append(f"| {name} | {value} | {risk} | {std_req} | {transport} |")
        
        return "\n".join(lines)