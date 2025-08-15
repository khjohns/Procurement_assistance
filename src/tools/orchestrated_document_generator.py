# src/tools/orchestrated_document_generator.py
"""
Orchestrated Document Generator - Genererer samlet anskaffelsesnotat 
basert på alle vurderinger fra orkestreringsmotoren.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

class OrchestratedDocumentGenerator:
    """Genererer samlet dokument fra orkestrert prosess."""
    
    def __init__(self, output_dir: str = "procurement_documents"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_from_context(self, orchestration_context: Dict[str, Any]) -> str:
        """
        Genererer dokument fra orchestration context.
        
        Args:
            orchestration_context: Komplett context fra ReasoningOrchestrator
            
        Returns:
            Filsti til generert dokument
        """
        # Ekstraher data fra context
        procurement_data = None
        triage_result = None
        oslomodell_result = None
        environmental_result = None
        
        # Finn procurement data
        if 'current_state' in orchestration_context:
            if 'request' in orchestration_context['current_state']:
                procurement_data = orchestration_context['current_state']['request']
        
        # Finn assessment resultater
        for exec_entry in orchestration_context.get('execution_history', []):
            action = exec_entry.get('action', {})
            result = exec_entry.get('result', {})
            
            if action.get('method') == 'agent.run_triage' and result.get('status') == 'success':
                triage_result = result.get('result')
            elif action.get('method') == 'agent.run_oslomodell' and result.get('status') == 'success':
                oslomodell_result = result.get('result')
            elif action.get('method') == 'agent.run_environmental' and result.get('status') == 'success':
                environmental_result = result.get('result')
        
        if not procurement_data:
            raise ValueError("No procurement data found in context")
        
        timestamp = datetime.now()
        doc_id = f"orchestrated_{procurement_data.get('id', 'unknown')}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Generer markdown-innhold
        content = self._generate_markdown_content(
            procurement_data,
            triage_result,
            oslomodell_result,
            environmental_result,
            timestamp
        )
        
        # Lagre dokument
        filename = f"{doc_id}.md"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(filepath)
    
    def _generate_markdown_content(self, 
                                  procurement: Dict[str, Any],
                                  triage: Optional[Dict[str, Any]],
                                  oslomodell: Optional[Dict[str, Any]],
                                  environmental: Optional[Dict[str, Any]],
                                  timestamp: datetime) -> str:
        """Genererer samlet markdown-innhold."""
        
        lines = []
        
        # Header
        lines.extend([
            f"# 📋 Samlet Anskaffelsesnotat",
            f"",
            f"**Generert:** {timestamp.strftime('%d.%m.%Y kl. %H:%M')}",
            f"**Type:** Komplett vurdering (Triage + Oslomodell + Miljøkrav)",
            f"",
            f"---",
            f""
        ])
        
        # Executive Summary
        lines.extend([
            f"## 📊 Sammendrag",
            f""
        ])
        
        # Triage status
        if triage:
            color = triage.get('color', 'UKJENT')
            color_emoji = {"GRØNN": "🟢", "GUL": "🟡", "RØD": "🔴"}.get(color, "⚪")
            lines.append(f"**Triage:** {color_emoji} {color}")
        
        # Oslomodell status
        if oslomodell:
            risk = oslomodell.get('vurdert_risiko_for_akrim', 'ukjent')
            lines.append(f"**Arbeidslivskriminalitet:** {risk.upper()}")
            lines.append(f"**Antall seriøsitetskrav:** {len(oslomodell.get('påkrevde_seriøsitetskrav', []))}")
        
        # Miljø status
        if environmental:
            env_risk = environmental.get('environmental_risk_level', 'ukjent')
            lines.append(f"**Miljørisiko:** {env_risk.upper()}")
        
        lines.extend(["", "---", ""])
        
        # Seksjon 1: Anskaffelsesinformasjon
        lines.extend([
            f"## 1. Anskaffelsesinformasjon",
            f"",
            f"### Grunndata",
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
        
        # Seksjon 2: Triage-vurdering
        if triage:
            lines.extend([
                f"## 2. Triage-vurdering",
                f"",
                f"### Klassifisering: {triage.get('color', 'UKJENT')}",
                f"",
                f"**Begrunnelse:** {triage.get('reasoning', 'Ikke oppgitt')}",
                f"",
                f"**Konfidens:** {triage.get('confidence', 0)*100:.0f}%",
                f""
            ])
            
            risk_factors = triage.get('risk_factors', [])
            if risk_factors:
                lines.extend([
                    f"### Risikofaktorer:",
                    f""
                ])
                for factor in risk_factors:
                    lines.append(f"- {factor}")
                lines.append("")
            
            lines.extend(["---", ""])
        
        # Seksjon 3: Oslomodell-vurdering
        if oslomodell:
            lines.extend([
                f"## 3. Oslomodell-vurdering",
                f"",
                f"### Arbeidslivskriminalitet",
                f"**Risikonivå:** {oslomodell.get('vurdert_risiko_for_akrim', 'ukjent').upper()}",
                f"",
                f"### Seriøsitetskrav ({len(oslomodell.get('påkrevde_seriøsitetskrav', []))} stk)",
                f""
            ])
            
            krav = oslomodell.get('påkrevde_seriøsitetskrav', [])
            if krav:
                lines.append("**Påkrevde krav:** " + ", ".join(sorted(krav)))
                lines.append("")
            
            # Underleverandører
            lines.extend([
                f"### Underleverandører",
                f"**Maks antall ledd:** {oslomodell.get('anbefalt_antall_underleverandørledd', 2)}",
                f""
            ])
            
            # Lærlinger
            apprentice = oslomodell.get('krav_om_lærlinger', {})
            if apprentice:
                lines.extend([
                    f"### Lærlinger",
                    f"**Status:** {'Påkrevd' if apprentice.get('status') else 'Ikke påkrevd'}",
                    f"**Begrunnelse:** {apprentice.get('begrunnelse', 'Ikke vurdert')}",
                    f""
                ])
            
            lines.extend(["---", ""])
        
        # Seksjon 4: Miljøvurdering
        if environmental:
            lines.extend([
                f"## 4. Miljøvurdering",
                f"",
                f"### Miljørisiko",
                f"**Nivå:** {environmental.get('environmental_risk_level', 'ukjent').upper()}",
                f"",
                f"### Standard miljøkrav",
                f"**Gjelder:** {'JA' if environmental.get('standard_miljokrav_applies') else 'NEI'}",
                f""
            ])
            
            # Transportkrav
            transport_reqs = environmental.get('transport_requirements', [])
            if transport_reqs:
                lines.extend([
                    f"### Transportkrav ({len(transport_reqs)} stk)",
                    f""
                ])
                for req in transport_reqs:
                    lines.append(f"- {req.get('requirement_type', 'Ukjent')}: {req.get('vehicle_class', 'Alle')}")
                lines.append("")
            
            lines.extend(["---", ""])
        
        # Seksjon 5: Samlet kravliste
        lines.extend([
            f"## 5. Samlet kravliste",
            f""
        ])
        
        all_requirements = []
        
        # Oslomodell-krav
        if oslomodell:
            for krav_code in oslomodell.get('påkrevde_seriøsitetskrav', []):
                all_requirements.append({
                    'type': 'Seriøsitet',
                    'kode': krav_code,
                    'kilde': 'Oslomodellen'
                })
        
        # Miljøkrav
        if environmental and environmental.get('standard_miljokrav_applies'):
            all_requirements.append({
                'type': 'Miljø',
                'kode': 'STD-MILJØ',
                'kilde': 'Miljøinstruks'
            })
        
        if all_requirements:
            lines.extend([
                f"| Type | Kode | Kilde |",
                f"|------|------|-------|"
            ])
            for req in all_requirements:
                lines.append(f"| {req['type']} | {req['kode']} | {req['kilde']} |")
            lines.append("")
        else:
            lines.append("Ingen spesifikke krav identifisert.")
            lines.append("")
        
        lines.extend(["---", ""])
        
        # Seksjon 6: Anbefalinger
        lines.extend([
            f"## 6. Samlede anbefalinger",
            f""
        ])
        
        all_recommendations = []
        
        if triage and triage.get('mitigation_measures'):
            all_recommendations.extend(triage['mitigation_measures'])
        
        if oslomodell and oslomodell.get('recommendations'):
            all_recommendations.extend(oslomodell['recommendations'])
        
        if environmental and environmental.get('recommendations'):
            all_recommendations.extend(environmental['recommendations'])
        
        if all_recommendations:
            # Fjern duplikater
            unique_recommendations = list(dict.fromkeys(all_recommendations))
            for rec in unique_recommendations:
                lines.append(f"- {rec}")
        else:
            lines.append("Ingen spesifikke anbefalinger.")
        
        lines.extend(["", "---", ""])
        
        # Seksjon 7: Handlingsplan
        lines.extend([
            f"## 7. Handlingsplan",
            f"",
            f"### Umiddelbare tiltak",
            f"- [ ] Gjennomgå alle identifiserte krav",
            f"- [ ] Utarbeide konkurransegrunnlag",
            f"- [ ] Planlegge markedsdialog hvis nødvendig",
            f"",
            f"### Før kontraktsinngåelse",
            f"- [ ] Verifisere leverandørdokumentasjon",
            f"- [ ] Gjennomføre prekvalifisering",
            f"- [ ] Etablere kontrollrutiner",
            f"",
            f"### Under kontraktsperioden",
            f"- [ ] Månedlig rapportering",
            f"- [ ] Kvartalsvise kontroller",
            f"- [ ] Årlig evaluering",
            f"",
            f"---",
            f""
        ])
        
        # Seksjon 8: Metadata
        lines.extend([
            f"## 8. Metadata",
            f"",
            f"### Vurderinger gjennomført:",
            f"- Triage: {'✅' if triage else '❌'}",
            f"- Oslomodell: {'✅' if oslomodell else '❌'}",
            f"- Miljøkrav: {'✅' if environmental else '❌'}",
            f"",
            f"**Dokumentversjon:** 1.0",
            f"**Status:** KOMPLETT",
            f"**Generert av:** Orchestrated Document Generator"
        ])
        
        return "\n".join(lines)