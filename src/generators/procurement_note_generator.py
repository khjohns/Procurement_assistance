# src/generators/procurement_note_generator.py

import yaml
from datetime import datetime
from typing import Dict, Any, List
import structlog
import re
from collections import defaultdict

from src.models.base_models import BaseProcurementInput, BaseAssessment, Requirement
from src.models.enums import ProcurementCategory, RiskType, RiskLevel
from src.builders.markdown_builder import MarkdownBuilder
from src.reporting.report_converter import ReportConverter
# --- NYTT: Importer den nye builderen ---
from src.builders.process_guidance_builder import ProcessGuidanceBuilder

logger = structlog.get_logger()

class ProcurementNoteGenerator:
    def __init__(self):
        self.content = self._load_yaml('config/procurement_note_content.yaml')
        self.structure = self._load_yaml('config/procurement_note_structure.yaml')
        self.converter = ReportConverter()
        self.process_builder = ProcessGuidanceBuilder()
        logger.info("ProcurementNoteGenerator initialized")
    
    def _load_yaml(self, path: str) -> Dict[str, Any]:
        with open(path, 'r', encoding='utf-8') as f: return yaml.safe_load(f)
    
    def generate(self, procurement: BaseProcurementInput, assessment: BaseAssessment, output_path: str) -> str:
        logger.info("Generating procurement note", procurement_id=procurement.procurement_id)
        context = self._build_context(procurement, assessment)
        builder = MarkdownBuilder()
        
        for section_config in self.structure['sections']:
            if self._should_include_section(section_config, context):
                section_content = self._build_section(section_config['id'], context)
                if section_content and section_content.content:
                    builder.content.extend(section_content.content)
        
        markdown = builder.build()
        
        if output_path.endswith('.md'):
            with open(output_path, 'w', encoding='utf-8') as f: f.write(markdown)
            logger.info("Markdown document generated", path=output_path)
        elif output_path.endswith('.docx'):
            self.converter.to_docx(markdown, output_path, reference_docx='config/word_templates/anskaffelsesnotat.docx')
            logger.info("Word document generated", path=output_path)
        else:
            logger.warning("Unsupported output format", path=output_path)
        return output_path
    
    def _build_context(self, procurement: BaseProcurementInput, assessment: BaseAssessment) -> Dict[str, Any]:
        # Denne konteksten vil nå bli sendt til ProcessGuidanceBuilder
        return {
            'procurement': procurement,
            'assessment': assessment,
            'has_supplier': bool(procurement.supplier_name_to_verify),
            'formatted': {
                'value': f"{procurement.value:,}".replace(',', ' '),
                'date': datetime.now().strftime('%d.%m.%Y'),
                'category': procurement.category.value.capitalize()
            },
            'grouped_requirements': self._group_requirements(assessment.applicable_requirements),
            'apprentice_trades': self._extract_apprentice_trades(assessment),
            'akrim_risk_level': self._determine_akrim_risk_level(procurement),
            'risk_details': self._summarize_risk_levels(procurement)
        }
    
    def _should_include_section(self, section_config: Dict, context: Dict) -> bool:
        return section_config.get('always', False)
    
    def _build_section(self, section_id: str, context: Dict) -> MarkdownBuilder:
        builder = MarkdownBuilder()
        if section_id == 'header': self._build_header_section(builder, context)
        elif section_id == 'metadata': self._build_metadata_section(builder, context)
        elif section_id == 'requirements':
            self._build_framework_section(builder, context)
            self._build_detailed_requirements_section(builder, context)
        elif section_id == 'risk_assessment': self._build_risk_section(builder, context)
        # --- NYTT: Delegering til den nye builderen ---
        elif section_id == 'process_guidance':
            return self.process_builder.build(context)
        elif section_id == 'contact':
            self._build_contact_section(builder, context)
        return builder

    # --- Hjelpemetoder (uendret fra forrige versjon) ---
    def _get_friendly_risk_name(self, risk_type: RiskType) -> str:
        if risk_type == RiskType.HUMAN_RIGHTS_AND_LAW: return "menneskerettigheter og folkerett"
        return risk_type.value.replace('-', ' og ').replace('_', ' ')

    def _summarize_risk_levels(self, procurement: BaseProcurementInput) -> str:
        due_diligence_risks = {RiskType.HUMAN_RIGHTS_AND_LAW, RiskType.CORRUPTION, RiskType.ENVIRONMENT, RiskType.WORKER_RIGHTS}
        risks_by_level = defaultdict(list)
        for item in procurement.risk_assessments:
            if item.type in due_diligence_risks:
                risks_by_level[item.level].append(self._get_friendly_risk_name(item.type))
        if not risks_by_level: return "ingen særskilt risiko for brudd på grunnleggende rettigheter"
        parts = []
        for level in [RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]:
            if level in risks_by_level:
                sorted_risks = sorted(risks_by_level[level])
                risk_names = ", ".join(sorted_risks[:-1]) + " og " + sorted_risks[-1] if len(sorted_risks) > 1 else sorted_risks[0]
                parts.append(f"**{level.value} risiko** for {risk_names}")
        return ", ".join(parts)

    def _determine_akrim_risk_level(self, procurement: BaseProcurementInput) -> str:
        relevant_risks = [item.level for item in procurement.risk_assessments if item.type in [RiskType.LABOR_CRIME, RiskType.SOCIAL_DUMPING]]
        if RiskLevel.HIGH in relevant_risks: return "høy"
        if RiskLevel.MEDIUM in relevant_risks: return "moderat"
        return "lav"

    def _extract_apprentice_trades(self, assessment: BaseAssessment) -> str:
        for step in assessment.reasoning_steps:
            match = re.search(r"Fagområder med 'særlig behov':\s*(.*)", step, re.IGNORECASE)
            if match: return match.group(1).strip().rstrip('.')
        return "Ingen spesifikke fag identifisert"

    def _group_requirements(self, requirements: List[Requirement]) -> Dict[str, List[Requirement]]:
        groups_config = self.content.get('requirement_groups', {})
        grouped = {name: [] for name in groups_config}
        for name, codes in groups_config.items():
            for req in requirements:
                if req.code in codes: grouped[name].append(req)
        return {name: reqs for name, reqs in grouped.items() if reqs}

    def _format_code_range(self, reqs: List[Requirement]) -> str:
        """Formaterer en liste med kravkoder til en kompakt streng, f.eks. 'A-U, V'."""
        if not reqs: return ""
        
        alpha_codes = sorted([r.code for r in reqs if len(r.code) == 1 and 'A' <= r.code <= 'Z'])
        non_alpha_codes = sorted([r.code for r in reqs if r.code not in alpha_codes])
        
        if not alpha_codes:
            return ", ".join(non_alpha_codes)

        ranges = []
        start = alpha_codes[0]
        
        for i in range(1, len(alpha_codes)):
            if ord(alpha_codes[i]) != ord(alpha_codes[i-1]) + 1:
                end = alpha_codes[i-1]
                ranges.append(f"{start}-{end}" if start != end else start)
                start = alpha_codes[i]
        
        end = alpha_codes[-1]
        ranges.append(f"{start}-{end}" if start != end else start)
        
        # Kombiner de formaterte rekkene med de ikke-alfabetiske kodene
        final_list = ranges + non_alpha_codes
        return ", ".join(final_list)

    # --- Seksjonsbyggere (uendret fra forrige versjon) ---
    def _build_header_section(self, builder: MarkdownBuilder, context: Dict):
        procurement = context['procurement']
        builder.add_heading(f"{self.content['titles']['main']}", 1)
        builder.add_paragraph(f"for kjøp av **{procurement.name}**")
        builder.add_horizontal_rule().add_line_breaks(1)
        header_lines = [f"**Dato:** {context['formatted']['date']}", f"**Anskaffelses-ID:** {procurement.procurement_id}"]
        builder.add_text_line("\n".join(header_lines))

    def _build_metadata_section(self, builder: MarkdownBuilder, context: Dict):
        procurement = context['procurement']
        builder.add_heading("Generelt om anskaffelsen", 2)
        
        saksbehandler = procurement.requested_by or "Ikke angitt"
        saksnr = procurement.case_number or "Ikke angitt"
        prosjektnr = procurement.project_number or "Ikke angitt"
        varighet = f"{procurement.duration_months} måned(er)"
        verdi = f"{context['formatted']['value']} NOK (eksl. mva.)"
        kategori = context['formatted']['category']
        
        # Manuell bygging for å unngå ekstra linjeskift
        builder.add_text_line("|  |  |  |  |")
        builder.add_text_line("|---|---|---|---|")
        rows = [
            ["**Saksbehandler:**", saksbehandler, "**Saksnr.:**", saksnr],
            ["**Avdeling:**", "Juridisk", "**Prosjektnr.:**", prosjektnr],
            ["**Prosedyre:**", "Forskriftens del I", "**Kategori:**", kategori],
            ["**Kontraktens varighet:**", varighet, "**Est. verdi:**", verdi]
        ]
        for row in rows:
            builder.add_text_line("| " + " | ".join(str(cell) for cell in row) + " |")
        
        builder.add_line_breaks(1)
        builder.add_text_line(f"**Anskaffelsen gjelder:**")
        builder.add_text_line(procurement.description or 'Ingen beskrivelse.')
        builder.add_line_breaks(1)
        builder.add_text_line(f"**Kort om behovet for anskaffelsen:**")
        builder.add_text_line(procurement.description or 'Ingen beskrivelse.')

    def _build_framework_section(self, builder: MarkdownBuilder, context: Dict):
        procurement = context['procurement']
        builder.add_heading("Overordnede rammer for anskaffelsen", 2)

        if procurement.value < 100000:
            text = self.content.get('standard_texts', {}).get('no_requirements_under_100k', '')
            builder.add_paragraph(text)
            return

        grouped_reqs = context.get('grouped_requirements', {})
        if not grouped_reqs:
            builder.add_paragraph("Ingen spesifikke kravsett ble aktivert.")
            return
        
        main_categories_to_show = ["Seriøsitetskrav", "Aktsomhetsvurderinger"]
        headers, rows = ["Kategori", "Krav", "Referanse"], []
        
        for group_name in main_categories_to_show:
            if group_name in grouped_reqs and grouped_reqs[group_name]:
                reqs = grouped_reqs[group_name]
                
                if group_name == "Seriøsitetskrav":
                    # --- NY LOGIKK: Skill V fra resten ---
                    seriøsitet_codes = [r for r in reqs if r.code != 'V']
                    lærling_krav_v = [r for r in reqs if r.code == 'V']
                    
                    display_parts = []
                    if seriøsitet_codes:
                        display_parts.append(self._format_code_range(seriøsitet_codes))
                    if lærling_krav_v:
                        display_parts.append('V')
                    
                    display = f"`{', '.join(display_parts)}`"
                    # --- SLUTT NY LOGIKK ---
                elif len(reqs) == 1:
                    display = reqs[0].name
                else:
                    display = ", ".join(sorted([r.code for r in reqs]))

                rows.append([group_name, display, "Instruks for Oslo kommunes anskaffelser pkt. xx"])
        
        if not rows: 
            builder.add_paragraph("Ingen av de overordnede kravene (Seriøsitet, Aktsomhet) ble aktivert.")
        else: 
            builder.add_table(headers, rows)

    def _build_detailed_requirements_section(self, builder: MarkdownBuilder, context: Dict):
        procurement = context['procurement']
        if procurement.value < 100000:
            return # Ikke vis denne seksjonen for småkjøp

        builder.add_heading("Særskilte krav å være oppmerksom på:", 3)
        key_req_codes = self.structure.get('key_requirements_to_detail', [])
        templates = self.content.get('detailed_requirement_texts', {})
        activated_reqs = context['assessment'].applicable_requirements
        found_key_reqs = False
        for req in sorted(activated_reqs, key=lambda r: r.code):
            if req.code in key_req_codes:
                found_key_reqs = True
                template = templates.get(req.code, templates.get('default', ''))
                template_data = {'req_name': req.name, 'req_description': req.description or "...", 'apprentice_trades': context.get('apprentice_trades', '...')}
                builder.add_text_line(f"* {template.format(**template_data)}")
        if not found_key_reqs: builder.add_paragraph("Ingen av de utvalgte nøkkelkravene ble aktivert.")
        else: builder.add_line_breaks(1)

    def _build_risk_section(self, builder: MarkdownBuilder, context: Dict):
        procurement = context['procurement']
        texts = self.content.get('risk_assessment_texts', {})
        builder.add_heading(texts.get('title', "Risiko"), 2)
        builder.add_paragraph(texts.get('intro_p1', ''))
        builder.add_paragraph(texts.get('intro_p2', '').format(risk_details=context.get('risk_details', '...')))
        if procurement.category != ProcurementCategory.GOODS:
            builder.add_paragraph(texts.get('non_goods_intro', ''))
            builder.add_paragraph(texts.get('non_goods_details', '').format(procurement_category=context['formatted']['category'], category_risk_level=context.get('akrim_risk_level', '...')))
        builder.add_horizontal_rule()

    def _build_contact_section(self, builder: MarkdownBuilder, context: Dict):
        """Bygger den avsluttende seksjonen med forbehold og kontaktinfo."""
        config = self.content.get('contact_section', {})
        
        builder.add_heading(config.get('title', "Kontakt"), 2)
        builder.add_paragraph(config.get('disclaimer', ''))
        builder.add_paragraph(config.get('contact_text', ''))