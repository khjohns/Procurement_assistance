# src/tools/comprehensive_document_generator.py
"""
Comprehensive Document Generator - Genererer fullstendige anskaffelsesnotater
ved bruk av ComprehensiveAssessment-modellen fra procurement_models.py.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.models.procurement_models import ComprehensiveAssessment

class ComprehensiveDocumentGenerator:
    """Genererer omfattende dokumenter basert på ComprehensiveAssessment."""
    
    def __init__(self, output_dir: str = "procurement_documents"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_from_assessment(self, assessment: ComprehensiveAssessment) -> str:
        """
        Genererer dokument fra ComprehensiveAssessment objekt.
        
        Args:
            assessment: ComprehensiveAssessment objekt
            
        Returns:
            Filsti til generert dokument
        """
        timestamp = datetime.now()
        doc_id = f"comprehensive_{assessment.procurement_request.id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Generer markdown-innhold
        content = self._generate_markdown_content(assessment, timestamp)
        
        # Lagre dokument
        filename = f"{doc_id}.md"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(filepath)
    
    def generate_from_context(self, orchestration_context: Dict[str, Any]) -> str:
        """
        Genererer dokument fra orchestration context ved å bygge ComprehensiveAssessment.
        
        Args:
            orchestration_context: Context fra ReasoningOrchestrator
            
        Returns:
            Filsti til generert dokument
        """
        # Bygg ComprehensiveAssessment fra context
        assessment = self._build_assessment_from_context(orchestration_context)
        return self.generate_from_assessment(assessment)
    
    def _build_assessment_from_context(self, context: Dict[str, Any]) -> ComprehensiveAssessment:
        """Bygger ComprehensiveAssessment fra orchestration context."""
        from src.models.procurement_models import (
            ProcurementRequest,
            OslomodellAssessmentResult,
            EnvironmentalAssessmentResult,
            TriageResult
        )
        
        # Finn procurement data
        procurement_data = None
        if 'current_state' in context:
            if 'request' in context['current_state']:
                procurement_data = context['current_state']['request']
        
        if not procurement_data:
            raise ValueError("No procurement data found in context")
        
        # Opprett ProcurementRequest
        procurement_request = ProcurementRequest(**procurement_data)
        
        # Finn assessment resultater
        triage_result = None
        oslomodell_result = None
        environmental_result = None
        
        for exec_entry in context.get('execution_history', []):
            action = exec_entry.get('action', {})
            result = exec_entry.get('result', {})
            
            if action.get('method') == 'agent.run_triage' and result.get('status') == 'success':
                triage_data = result.get('result')
                if triage_data:
                    triage_result = TriageResult(**triage_data)
            
            elif action.get('method') == 'agent.run_oslomodell' and result.get('status') == 'success':
                oslo_data = result.get('result')
                if oslo_data:
                    oslomodell_result = OslomodellAssessmentResult(**oslo_data)
            
            elif action.get('method') == 'agent.run_environmental' and result.get('status') == 'success':
                env_data = result.get('result')
                if env_data:
                    environmental_result = EnvironmentalAssessmentResult(**env_data)
        
        # Beregn samlet anbefaling
        overall_recommendation = self._generate_overall_recommendation(
            triage_result, oslomodell_result, environmental_result
        )
        
        # Tell totalt antall krav
        total_requirements = 0
        if oslomodell_result:
            total_requirements += len(oslomodell_result.påkrevde_seriøsitetskrav)
        if environmental_result and environmental_result.standard_miljokrav_applies:
            total_requirements += 1  # Standard miljøkrav teller som ett
        
        # Beregn compliance score (eksempel)
        compliance_score = self._calculate_compliance_score(
            triage_result, oslomodell_result, environmental_result
        )
        
        # Opprett ComprehensiveAssessment
        return ComprehensiveAssessment(
            procurement_request=procurement_request,
            oslomodell_result=oslomodell_result,
            miljokrav_result=environmental_result,
            triage_result=triage_result,
            protocol_result=None,  # Kan legges til senere
            overall_recommendation=overall_recommendation,
            total_requirements_count=total_requirements,
            compliance_score=compliance_score
        )
    
    def _generate_overall_recommendation(self, 
                                        triage: Optional[Any],
                                        oslomodell: Optional[Any],
                                        environmental: Optional[Any]) -> str:
        """Genererer samlet anbefaling basert på alle vurderinger."""
        recommendations = []
        
        if triage and triage.color == "RØD":
            recommendations.append("Høy-risiko anskaffelse krever full compliance-prosess")
        elif triage and triage.color == "GUL":
            recommendations.append("Moderat risiko - standard prosess med nøye oppfølging")
        else:
            recommendations.append("Lav-risiko anskaffelse - forenklet prosess kan vurderes")
        
        if oslomodell and oslomodell.vurdert_risiko_for_akrim == "høy":
            recommendations.append("Omfattende seriøsitetskrav påkrevd grunnet høy akrim-risiko")
        
        if environmental and environmental.environmental_risk_level == "høy":
            recommendations.append("Strenge miljøkrav må implementeres")
        
        return " | ".join(recommendations)
    
    def _calculate_compliance_score(self,
                                   triage: Optional[Any],
                                   oslomodell: Optional[Any],
                                   environmental: Optional[Any]) -> float:
        """Beregner en samlet compliance score (0.0-1.0)."""
        scores = []
        
        if triage:
            # Grønn = 1.0, Gul = 0.7, Rød = 0.4
            color_scores = {"GRØNN": 1.0, "GUL": 0.7, "RØD": 0.4}
            scores.append(color_scores.get(triage.color, 0.5))
        
        if oslomodell:
            # Jo flere krav, desto bedre compliance
            krav_score = min(len(oslomodell.påkrevde_seriøsitetskrav) / 22, 1.0)
            scores.append(krav_score)
        
        if environmental:
            # Standard miljøkrav = god compliance
            env_score = 1.0 if environmental.standard_miljokrav_applies else 0.5
            scores.append(env_score)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _generate_markdown_content(self, 
                                  assessment: ComprehensiveAssessment,
                                  timestamp: datetime) -> str:
        """Genererer markdown-innhold fra ComprehensiveAssessment."""
        
        lines = []
        proc = assessment.procurement_request
        
        # Header med emoji
        lines.extend([
            f"# 📊 Fullstendig Anskaffelsesnotat",
            f"",
            f"**Generert:** {timestamp.strftime('%d.%m.%Y kl. %H:%M')}",
            f"**Type:** ComprehensiveAssessment",
            f"**Compliance Score:** {assessment.compliance_score*100:.1f}%",
            f"",
            f"---",
            f""
        ])
        
        # Executive Dashboard
        lines.extend([
            f"## 🎯 Executive Dashboard",
            f"",
            f"| Metrikk | Verdi |",
            f"|---------|-------|"
        ])
        
        lines.append(f"| **Anskaffelse** | {proc.name} |")
        lines.append(f"| **Verdi** | {proc.value:,} NOK |")
        lines.append(f"| **Kategori** | {proc.category.value} |")
        lines.append(f"| **Varighet** | {proc.duration_months} mnd |")
        
        if assessment.triage_result:
            color_emoji = {"GRØNN": "🟢", "GUL": "🟡", "RØD": "🔴"}.get(
                assessment.triage_result.color.value, "⚪"
            )
            lines.append(f"| **Triage** | {color_emoji} {assessment.triage_result.color.value} |")
        
        if assessment.oslomodell_result:
            lines.append(f"| **Akrim-risiko** | {assessment.oslomodell_result.vurdert_risiko_for_akrim.upper()} |")
        
        if assessment.miljokrav_result:
            lines.append(f"| **Miljørisiko** | {assessment.miljokrav_result.environmental_risk_level.value.upper()} |")
        
        lines.append(f"| **Totalt antall krav** | {assessment.total_requirements_count} |")
        lines.append(f"| **Compliance Score** | {assessment.compliance_score*100:.1f}% |")
        
        lines.extend(["", "---", ""])
        
        # Samlet anbefaling
        lines.extend([
            f"## 💡 Samlet anbefaling",
            f"",
            f"> {assessment.overall_recommendation}",
            f"",
            f"---",
            f""
        ])
        
        # Detaljert anskaffelsesinformasjon
        lines.extend([
            f"## 📋 Detaljert anskaffelsesinformasjon",
            f"",
            f"### Grunndata",
            f"- **ID:** {proc.id}",
            f"- **Navn:** {proc.name}",
            f"- **Beskrivelse:** {proc.description or 'Ikke oppgitt'}",
            f"- **Verdi:** {proc.value:,} NOK ekskl. mva",
            f"- **Kategori:** {proc.category.value}",
            f"- **Varighet:** {proc.duration_months} måneder",
            f""
        ])
        
        if proc.includes_construction:
            lines.extend([
                f"### Bygge-/anleggsdata",
                f"- **Byggeplassstørrelse:** {proc.construction_site_size or 'Ikke oppgitt'} m²",
                f"- **Inkluderer riving:** {'Ja' if proc.involves_demolition else 'Nei'}",
                f"- **Inkluderer grunnarbeid:** {'Ja' if proc.involves_earthworks else 'Nei'}",
                f""
            ])
        
        if proc.involves_transport:
            lines.extend([
                f"### Transportdata",
                f"- **Transporttype:** {proc.transport_type.value}",
                f"- **Estimert volum:** {proc.estimated_transport_volume or 'Ikke oppgitt'}",
                f""
            ])
        
        lines.extend(["---", ""])
        
        # Triage-resultater
        if assessment.triage_result:
            triage = assessment.triage_result
            lines.extend([
                f"## 🚦 Triage-vurdering",
                f"",
                f"**Klassifisering:** {triage.color.value}",
                f"**Konfidens:** {triage.confidence*100:.0f}%",
                f"",
                f"**Begrunnelse:** {triage.reasoning}",
                f""
            ])
            
            if triage.risk_factors:
                lines.extend([
                    f"### Risikofaktorer:",
                    f""
                ])
                for factor in triage.risk_factors:
                    lines.append(f"- {factor}")
                lines.append("")
            
            lines.extend(["---", ""])
        
        # Oslomodell-resultater
        if assessment.oslomodell_result:
            oslo = assessment.oslomodell_result
            lines.extend([
                f"## 🏛️ Oslomodell-vurdering",
                f"",
                f"**Arbeidslivskriminalitet:** {oslo.vurdert_risiko_for_akrim.upper()}",
                f"**Antall seriøsitetskrav:** {len(oslo.påkrevde_seriøsitetskrav)}",
                f"**Underleverandørledd:** {oslo.anbefalt_antall_underleverandørledd}",
                f""
            ])
            
            if oslo.påkrevde_seriøsitetskrav:
                lines.extend([
                    f"### Påkrevde seriøsitetskrav:",
                    f"**Koder:** {', '.join(sorted(oslo.påkrevde_seriøsitetskrav))}",
                    f""
                ])
            
            if oslo.krav_om_lærlinger:
                lines.extend([
                    f"### Lærlinger:",
                    f"**Status:** {'Påkrevd' if oslo.krav_om_lærlinger.get('status') else 'Ikke påkrevd'}",
                    f"**Begrunnelse:** {oslo.krav_om_lærlinger.get('begrunnelse', 'Ikke vurdert')}",
                    f""
                ])
            
            lines.extend(["---", ""])
        
        # Miljøresultater
        if assessment.miljokrav_result:
            env = assessment.miljokrav_result
            lines.extend([
                f"## 🌱 Miljøvurdering",
                f"",
                f"**Miljørisiko:** {env.environmental_risk_level.value.upper()}",
                f"**Standard miljøkrav:** {'JA' if env.standard_miljokrav_applies else 'NEI'}",
                f""
            ])
            
            if env.transport_requirements:
                lines.extend([
                    f"### Transportkrav ({len(env.transport_requirements)} stk):",
                    f""
                ])
                for req in env.transport_requirements:
                    lines.append(f"- {req.requirement_type.value}: {req.vehicle_class}")
                lines.append("")
            
            lines.extend(["---", ""])
        
        # Aggregerte krav
        all_requirements = assessment.aggregate_requirements()
        if all_requirements:
            lines.extend([
                f"## 📑 Alle krav ({len(all_requirements)} stk)",
                f"",
                f"| Kode | Kategori | Kilde | Obligatorisk |",
                f"|------|----------|-------|--------------|"
            ])
            
            for req in all_requirements:
                mandatory = "Ja" if req.is_mandatory else "Nei"
                lines.append(f"| {req.code} | {req.category.value} | {req.source.value} | {mandatory} |")
            
            lines.extend(["", "---", ""])
        
        # Handlingsplan
        lines.extend([
            f"## 📝 Handlingsplan",
            f"",
            f"### Fase 1: Forberedelse",
            f"- [ ] Gjennomgå alle {assessment.total_requirements_count} identifiserte krav",
            f"- [ ] Utarbeide detaljert konkurransegrunnlag",
            f"- [ ] Gjennomføre markedsdialog",
            f"",
            f"### Fase 2: Konkurranse",
            f"- [ ] Publisere konkurranse med alle krav",
            f"- [ ] Gjennomføre prekvalifisering",
            f"- [ ] Evaluere tilbud",
            f"",
            f"### Fase 3: Kontraktsoppfølging",
            f"- [ ] Etablere kontrollrutiner",
            f"- [ ] Implementere rapporteringssystem",
            f"- [ ] Gjennomføre periodiske revisjoner",
            f"",
            f"---",
            f""
        ])
        
        # Metadata og sporbarhet
        lines.extend([
            f"## 🔍 Metadata og sporbarhet",
            f"",
            f"**Opprettet:** {assessment.created_at}",
            f"**Dokumentversjon:** 2.0",
            f"**Status:** KOMPLETT",
            f"**Generator:** ComprehensiveDocumentGenerator",
            f"",
            f"### Vurderinger inkludert:",
            f"- Triage: {'✅' if assessment.triage_result else '❌'}",
            f"- Oslomodell: {'✅' if assessment.oslomodell_result else '❌'}",
            f"- Miljøkrav: {'✅' if assessment.miljokrav_result else '❌'}",
            f"- Protokoll: {'✅' if assessment.protocol_result else '❌'}"
        ])
        
        return "\n".join(lines)