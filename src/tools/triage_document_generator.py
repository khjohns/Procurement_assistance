# src/tools/triage_document_generator.py
"""
Triage Document Generator - Genererer strukturerte notater for triage-vurderinger.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

class TriageDocumentGenerator:
    """Genererer markdown-dokumenter for triage-vurderinger."""
    
    def __init__(self, output_dir: str = "procurement_documents"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_document(self, procurement_data: Dict[str, Any], 
                         triage_result: Dict[str, Any]) -> str:
        """
        Genererer triage-notat.
        
        Args:
            procurement_data: Data om anskaffelsen
            triage_result: Resultat fra triage-vurdering
            
        Returns:
            Filsti til generert dokument
        """
        timestamp = datetime.now()
        doc_id = f"triage_{procurement_data.get('id', 'unknown')}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Generer markdown-innhold
        content = self._generate_markdown_content(
            procurement_data, 
            triage_result,
            timestamp
        )
        
        # Lagre dokument
        filename = f"{doc_id}.md"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(filepath)
    
    def _generate_markdown_content(self, procurement: Dict[str, Any], 
                                  triage: Dict[str, Any],
                                  timestamp: datetime) -> str:
        """Genererer markdown-innhold for triage-dokumentet."""
        
        lines = []
        
        # Header
        lines.extend([
            f"# Triage-vurdering",
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
            f"**ID:** {procurement.get('id', 'Ikke oppgitt')}",
            f"**Navn:** {procurement.get('name', 'Ikke oppgitt')}",
            f"**Verdi:** {procurement.get('value', 0):,} NOK ekskl. mva",
            f"**Kategori:** {procurement.get('category', 'Ikke spesifisert')}",
            f"**Varighet:** {procurement.get('duration_months', 0)} måneder",
            f"",
            f"**Beskrivelse:**",
            f"> {procurement.get('description', 'Ingen beskrivelse oppgitt')}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 2: Triage-klassifisering
        color = triage.get('color', 'UKJENT')
        color_emoji = {"GRØNN": "🟢", "GUL": "🟡", "RØD": "🔴"}.get(color, "⚪")
        
        lines.extend([
            f"## 2. Triage-klassifisering",
            f"",
            f"### Resultat: {color_emoji} **{color}**",
            f"",
            f"**Konfidens:** {triage.get('confidence', 0)*100:.0f}%",
            f"",
            f"### Begrunnelse:",
            f"> {triage.get('reasoning', 'Ingen begrunnelse oppgitt')}",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 3: Risikofaktorer
        risk_factors = triage.get('risk_factors', [])
        if risk_factors:
            lines.extend([
                f"## 3. Identifiserte risikofaktorer",
                f""
            ])
            for factor in risk_factors:
                lines.append(f"- {factor}")
            lines.extend(["", "---", ""])
        
        # Seksjon 4: Risikoreduserende tiltak
        mitigation = triage.get('mitigation_measures', [])
        if mitigation:
            lines.extend([
                f"## 4. Anbefalte risikoreduserende tiltak",
                f""
            ])
            for measure in mitigation:
                lines.append(f"- {measure}")
            lines.extend(["", "---", ""])
        
        # Seksjon 5: Spesielle hensyn
        lines.extend([
            f"## 5. Spesielle hensyn",
            f""
        ])
        
        if triage.get('requires_special_attention', False):
            lines.extend([
                f"⚠️ **KREVER SPESIELL OPPMERKSOMHET**",
                f""
            ])
        
        if triage.get('escalation_recommended', False):
            lines.extend([
                f"⚠️ **ESKALERING ANBEFALES**",
                f"",
                f"Denne anskaffelsen bør gjennomgås av overordnet nivå.",
                f""
            ])
        
        if not triage.get('requires_special_attention') and not triage.get('escalation_recommended'):
            lines.append("Ingen spesielle hensyn identifisert.")
        
        lines.extend(["", "---", ""])
        
        # Seksjon 6: Videre prosess
        lines.extend([
            f"## 6. Anbefalt videre prosess",
            f""
        ])
        
        if color == "GRØNN":
            lines.extend([
                f"### Forenklet prosess",
                f"- Direkte anskaffelse kan gjennomføres",
                f"- Minimale kontrollkrav",
                f"- Standard dokumentasjon"
            ])
        elif color == "GUL":
            lines.extend([
                f"### Standard prosess",
                f"- Konkurranseutsetting anbefales",
                f"- Standard seriøsitetskrav (A-E)",
                f"- Vurder ytterligere krav ved behov",
                f"- Normal oppfølging og kontroll"
            ])
        elif color == "RØD":
            lines.extend([
                f"### Omfattende prosess",
                f"- Full konkurranseutsetting påkrevd",
                f"- Alle relevante seriøsitetskrav må vurderes",
                f"- Grundig prekvalifisering av leverandører",
                f"- Tett oppfølging under kontraktsperioden",
                f"- Vurder ekstern bistand ved behov"
            ])
        
        lines.extend(["", "---", ""])
        
        # Seksjon 7: Sjekkliste
        lines.extend([
            f"## 7. Sjekkliste for videre arbeid",
            f""
        ])
        
        if color == "GRØNN":
            lines.extend([
                f"- [ ] Verifiser at verdi er under 100.000 kr",
                f"- [ ] Dokumenter anskaffelsen",
                f"- [ ] Innhent tilbud fra minst én leverandør"
            ])
        elif color == "GUL":
            lines.extend([
                f"- [ ] Gjennomfør markedsundersøkelse",
                f"- [ ] Utarbeid konkurransegrunnlag",
                f"- [ ] Fastsett evalueringskriterier",
                f"- [ ] Vurder behov for seriøsitetskrav",
                f"- [ ] Planlegg kontraktsoppfølging"
            ])
        elif color == "RØD":
            lines.extend([
                f"- [ ] Gjennomfør full Oslomodell-vurdering",
                f"- [ ] Vurder miljøkrav",
                f"- [ ] Utarbeid detaljert konkurransegrunnlag",
                f"- [ ] Etabler evalueringskomité",
                f"- [ ] Planlegg prekvalifisering",
                f"- [ ] Forbered kontraktsoppfølgingsplan",
                f"- [ ] Vurder behov for ekstern bistand"
            ])
        
        lines.extend(["", "---", ""])
        
        # Seksjon 8: Metadata
        lines.extend([
            f"## 8. Metadata",
            f"",
            f"**Vurdert av:** {triage.get('assessed_by', 'triage_agent')}",
            f"**Dokumentversjon:** 1.0",
            f"**Status:** FERDIG",
            f"**Triage-ID:** {triage.get('assessment_id', 'Ikke oppgitt')}"
        ])
        
        return "\n".join(lines)
    
    def generate_summary_table(self, assessments: List[Dict[str, Any]]) -> str:
        """Genererer oppsummeringstabell for flere triage-vurderinger."""
        lines = []
        lines.extend([
            "| Anskaffelse | Verdi (NOK) | Klassifisering | Konfidens | Eskalering |",
            "|-------------|-------------|----------------|-----------|------------|"
        ])
        
        for a in assessments:
            proc = a.get('procurement', {})
            triage = a.get('triage', {})
            
            name = proc.get('name', 'Ukjent')[:30]
            value = f"{proc.get('value', 0):,}"
            color = triage.get('color', 'UKJENT')
            confidence = f"{triage.get('confidence', 0)*100:.0f}%"
            escalation = "Ja" if triage.get('escalation_recommended', False) else "Nei"
            
            lines.append(f"| {name} | {value} | {color} | {confidence} | {escalation} |")
        
        return "\n".join(lines)