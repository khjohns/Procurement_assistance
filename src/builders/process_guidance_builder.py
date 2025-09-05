# src/builders/process_guidance_builder.py
import yaml
from typing import Dict, Any, Optional

from src.builders.markdown_builder import MarkdownBuilder
from src.models.base_models import BaseProcurementInput

class ProcessGuidanceBuilder:
    def __init__(self, content_path: str = 'config/process_guidance_content.yaml'):
        with open(content_path, 'r', encoding='utf-8') as f:
            self.content = yaml.safe_load(f)['process_guidance']
        self.base_url = "https://tqm3.tqmenterprise.no/oslobygg/Publishing/Document/LoadLocalContent/"

    def build(self, context: Dict[str, Any]) -> MarkdownBuilder:
        builder = MarkdownBuilder()
        procurement: BaseProcurementInput = context['procurement']
        
        builder.add_heading("Veiledning for videre prosess", 2)

        if procurement.supplier_name_to_verify:
            self._build_with_supplier_scenario(builder, procurement)
        else:
            intro_config = self.content['intro']
            procedure_resource = {"name": intro_config['procedure_name'], "id": intro_config['procedure_id']}
            procedure_link = self._format_link(procedure_resource)
            intro_text = intro_config['text'].format(procedure_link=procedure_link)
            builder.add_paragraph(intro_text) # add_paragraph gir fin spacing her
            self._build_standard_guidance(builder, procurement)
        
        return builder

    def _build_with_supplier_scenario(self, builder: MarkdownBuilder, procurement: BaseProcurementInput):
        scenario = self.content['with_supplier']
        
        # Fase 1
        phase1 = scenario['phase_1']
        builder.add_heading(phase1['title'], 3)
        
        step1 = phase1['steps']['competition_assessment']
        step2 = phase1['steps']['habilitet']
        
        # --- OPPRYDDING: Bruk tight=True for å kontrollere spacing ---
        checklist_items = [
            {'text': f"**Trinn {step1['number']}: {step1['title']}**"},
            {'text': f"**Trinn {step2['number']}: {step2['title']}**"}
        ]
        builder.add_checklist(checklist_items, tight=True)

        # Verdi-basert advarsel
        if procurement.value > 500000:
            data = step1['thresholds']['over_500k']
            builder.add_paragraph(f"{data.get('icon', '')} **{data.get('title', '')}:** {data.get('main_text', '')}")
            builder.add_paragraph(f"**{data.get('action', '')}**")
            builder.add_paragraph(data.get('documentation_note', ''))
        elif procurement.value > 100000:
            data = step1['thresholds']['over_100k']
            builder.add_paragraph(f"{data.get('icon', '')} **{data.get('title', '')}:** {data.get('main_text', '')}")
            builder.add_paragraph(data.get('supplier_specific', '').format(supplier_name=procurement.supplier_name_to_verify))
            builder.add_paragraph(data.get('documentation_note', ''))
        else:
            data = step1['thresholds']['under_100k']
            builder.add_paragraph(f"{data.get('icon', '')} **{data.get('title', '')}:** {data.get('main_text', '').format(supplier_name=procurement.supplier_name_to_verify)}")
            builder.add_paragraph(data.get('additional', ''))

        # Fase 2
        phase2 = scenario['phase_2']
        builder.add_heading(phase2['title'], 3)

        checklist_items = []
        if procurement.value > 100000:
            step3 = phase2['steps']['protocol']
            checklist_items.append({'text': f"**Trinn {step3['number']}: {step3['title']}**"})
        
        step4 = phase2['steps']['contract']
        checklist_items.append({'text': f"**Trinn {step4['number']}: {step4['title']}**"})
        builder.add_checklist(checklist_items, tight=True)

        # Detaljer om kontrakt/bestilling
        if procurement.value > 500000:
            variant = step4['variants']['formal_contract']
            builder.add_list([variant.get('text', '')] + variant.get('requirements', []))
        else:
            variant = step4['variants']['order_letter']
            details = [variant.get('text', '')]
            note = variant.get('note')
            if note: details.append(note)
            builder.add_list(details)
        
        builder.add_paragraph(step4.get('signature_reminder', ''))

    def _build_standard_guidance(self, builder: MarkdownBuilder, procurement: BaseProcurementInput):
        scenario = self.content['standard_guidance']
        
        # Fase 1
        phase1 = scenario['phase_1']
        builder.add_heading(phase1['title'], 3)
        
        step1 = phase1['steps']['framework_check']
        link_ramme = self._format_link(step1['resources']['rammeavtale'])
        link_samkjop = self._format_link(step1['resources']['samkjop'])
        desc1 = step1['description'].format(link_rammeavtale=link_ramme, link_samkjop=link_samkjop)
        builder.add_nested_checklist_item(title=f"**Trinn {step1['number']}: {step1['title']}**", sub_items=[desc1])

        step2 = phase1['steps']['habilitet']
        link_veil = self._format_link(step2['resources']['veiledning'])
        link_sjekk = self._format_link(step2['resources']['sjekkliste'])
        desc2 = step2['description'].format(link_veiledning=link_veil, link_sjekkliste=link_sjekk)
        builder.add_nested_checklist_item(title=f"**Trinn {step2['number']}: {step2['title']}**", sub_items=[desc2])
        builder.add_line_breaks(1)

        # Fase 2
        phase2 = scenario['phase_2']
        builder.add_heading(phase2['title'], 3)
        
        step3 = phase2['steps']['competition_need']
        desc3 = step3['description_over_500k'] if procurement.value > 500000 else step3['description_under_500k']
        builder.add_nested_checklist_item(title=f"**Trinn {step3['number']}: {step3['title']}**", sub_items=[desc3])
        
        if procurement.value > 100000:
            step4 = phase2['steps']['protocol']
            link_protokoll = self._format_link(step4['template'])
            desc4 = step4['description'].format(link_protokoll=link_protokoll)
            builder.add_nested_checklist_item(title=f"**Trinn {step4['number']}: {step4['title']}**", sub_items=[desc4])
        builder.add_line_breaks(1)

        # Fase 3
        phase3 = scenario['phase_3']
        builder.add_heading(phase3['title'], 3)

        step5 = phase3['steps']['contract']
        sub_items = []
        if procurement.value > 500000:
            sub_items.append(step5['description_over_500k'])
            sub_items.extend(step5['requirements'])
        else:
             sub_items.append(step5['description_under_500k'])
        builder.add_nested_checklist_item(title=f"**Trinn {step5['number']}: {step5['title']}**", sub_items=sub_items)
        builder.add_line_breaks(1)

    def _format_link(self, resource: Dict) -> str:
        name = resource.get('name', 'Lenke')
        doc_id = resource.get('id')
        url = f"{self.base_url}{doc_id}" if doc_id else resource.get('url', '#')
        display_name = name
        if doc_id and doc_id not in name:
             display_name = f"{name} (ID: {doc_id})"
        return f"[{display_name}]({url})"