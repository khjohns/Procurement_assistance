#!/usr/bin/env python3
"""
oslomodell_document_generator.py
Genererer strukturerte anskaffelsesnotater basert på Oslomodell-vurderinger.
Produserer markdown-dokumenter med alle relevante krav og anbefalinger.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import structlog

logger = structlog.get_logger()

class OslomodellDocumentGenerator:
    """
    Genererer strukturerte dokumenter basert på Oslomodell-vurderinger.
    Produserer markdown-filer med komplett oversikt over krav og anbefalinger.
    """
    
    def __init__(self, output_dir: str = "generated_documents"):
        """
        Args:
            output_dir: Mappe hvor dokumenter skal lagres
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Mal for kravbeskrivelser
        self.krav_beskrivelser = {
            "A": "HMS-egenerklæring",
            "B": "Skatteattest",
            "C": "Bekreftelse på betaling av arbeidsgiveravgift og merverdiavgift",
            "D": "Bekreftelse på tegning av yrkesskadeforsikring",
            "E": "Bekreftelse på ansettelsesforhold i henhold til norsk lov",
            "F": "Pliktig medlemskap i StartBANK/leverandørregister",
            "G": "Faglærte håndverkere",
            "H": "Begrensning av antall ledd i leverandørkjeden",
            "I": "Krav til lønns- og arbeidsvilkår",
            "J": "Krav til lønns- og arbeidsvilkår for underleverandører",
            "K": "Rapportering av lønns- og arbeidsvilkår",
            "L": "Krav om bruk av fast ansatte",
            "M": "Bruk av lærlinger",
            "N": "Internkontroll for sikkerhet, helse og arbeidsmiljø",
            "O": "Arbeidstilsynets pålegg",
            "P": "Norskkunnskaper for nøkkelpersonell",
            "Q": "Elektronisk personalregistrering",
            "R": "HMS-kort",
            "S": "Krav om forsvarlig innkvartering",
            "T": "Krav om etisk handel",
            "U": "Dokumentasjon på etterlevelse av lønns- og arbeidsvilkår",
            "V": "Lærlinger (over terskelverdi)"
        }
        
        # Kategoribeskrivelser
        self.kategori_beskrivelser = {
            "bygge": "Byggearbeider",
            "anlegg": "Anleggsarbeider",
            "renhold": "Renhold",
            "tjeneste": "Tjenesteanskaffelse",
            "vare": "Vareanskaffelse",
            "konsulent": "Konsulenttjenester",
            "it": "IT-tjenester"
        }
    
    def generate_document(self, 
                         procurement_data: Dict[str, Any],
                         oslomodell_assessment: Dict[str, Any],
                         additional_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Genererer komplett anskaffelsesnotat.
        
        Args:
            procurement_data: Info om anskaffelsen
            oslomodell_assessment: Vurdering fra Oslomodell-agent
            additional_context: Eventuell tilleggsinformasjon
            
        Returns:
            Filsti til generert dokument
        """
        logger.info("Generating procurement document",
                   procurement_name=procurement_data.get('name'))
        
        # Generer filnavn
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in procurement_data.get('name', 'ukjent')[:30] 
                           if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{timestamp}_{safe_name}_oslomodell_notat.md"
        filepath = self.output_dir / filename
        
        # Generer innhold
        content = self._generate_markdown_content(
            procurement_data, 
            oslomodell_assessment,
            additional_context
        )
        
        # Skriv til fil
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Document generated: {filepath}")
        return str(filepath)
    
    def _generate_markdown_content(self,
                                  procurement: Dict[str, Any],
                                  assessment: Dict[str, Any],
                                  context: Optional[Dict[str, Any]] = None) -> str:
        """
        Genererer markdown-innhold for notatet.
        """
        # Start dokument
        lines = [
            f"# Anskaffelsesnotat - Oslomodellen",
            f"\n**Generert:** {datetime.now().strftime('%d.%m.%Y kl. %H:%M')}",
            f"\n---\n"
        ]
        
        # Seksjon 1: Anskaffelsesinformasjon
        lines.extend([
            "## 1. Anskaffelsesinformasjon\n",
            f"**Navn:** {procurement.get('name', 'Ikke spesifisert')}",
            f"**Verdi:** {procurement.get('value', 0):,} NOK ekskl. mva",
            f"**Kategori:** {self.kategori_beskrivelser.get(procurement.get('category', ''), procurement.get('category', 'Ukjent'))}",
            f"**Varighet:** {procurement.get('duration_months', 0)} måneder",
            f"\n**Beskrivelse:**",
            f"> {procurement.get('description', 'Ingen beskrivelse oppgitt')}",
            "\n---\n"
        ])
        
        # Seksjon 2: Risikovurdering
        risk_level = assessment.get('vurdert_risiko_for_akrim', 'ikke vurdert')
        risk_emoji = {"høy": "🔴", "moderat": "🟡", "lav": "🟢"}.get(risk_level, "⚪")
        
        lines.extend([
            "## 2. Risikovurdering\n",
            f"**Vurdert risiko for arbeidslivskriminalitet:** {risk_emoji} **{risk_level.upper()}**",
            f"\n**Vurderingsgrunnlag:**"
        ])
        
        # Vis reasoning hvis tilgjengelig
        if assessment.get('reasoning_details'):
            for key, value in assessment['reasoning_details'].items():
                lines.append(f"- {value}")
        
        lines.append("\n---\n")
        
        # Seksjon 3: Seriøsitetskrav
        krav_list = assessment.get('påkrevde_seriøsitetskrav', [])
        
        lines.extend([
            "## 3. Påkrevde seriøsitetskrav\n",
            f"**Antall krav:** {len(krav_list)} stk",
            f"**Hjemmel:** Instruks for Oslo kommunes anskaffelser, punkt 4",
            "\n### Kravliste:\n"
        ])
        
        # Grupper krav
        basis_krav = [k for k in krav_list if k in ['A', 'B', 'C', 'D', 'E']]
        risiko_krav = [k for k in krav_list if k in ['F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U']]
        spesial_krav = [k for k in krav_list if k == 'V']
        
        if basis_krav:
            lines.append("#### Basiskrav (alltid påkrevd):")
            for krav in sorted(basis_krav):
                lines.append(f"- **Krav {krav}:** {self.krav_beskrivelser.get(krav, 'Ukjent krav')}")
        
        if risiko_krav:
            lines.append("\n#### Tilleggskrav (basert på kategori/risiko):")
            for krav in sorted(risiko_krav):
                lines.append(f"- **Krav {krav}:** {self.krav_beskrivelser.get(krav, 'Ukjent krav')}")
        
        if spesial_krav:
            lines.append("\n#### Spesialkrav:")
            for krav in spesial_krav:
                lines.append(f"- **Krav {krav}:** {self.krav_beskrivelser.get(krav, 'Ukjent krav')}")
        
        lines.append("\n---\n")
        
        # Seksjon 4: Underleverandører
        max_ledd = assessment.get('anbefalt_antall_underleverandørledd', -1)
        
        lines.extend([
            "## 4. Begrensning av underleverandører\n",
            f"**Maks antall ledd i vertikal kjede:** {max_ledd} {'ledd' if max_ledd == 1 else 'ledd'}",
            f"**Hjemmel:** Instruks punkt 5.1",
            f"\n**Begrunnelse:**"
        ])
        
        if max_ledd == 0:
            lines.append("> Ved høy risiko kan bruk av underleverandører nektes helt")
        elif max_ledd == 1:
            lines.append("> Ved moderat til høy risiko tillates maksimalt ett ledd underleverandører")
        elif max_ledd == 2:
            lines.append("> Ved lav risiko kan det åpnes for to ledd underleverandører")
        
        lines.append("\n---\n")
        
        # Seksjon 5: Lærlinger
        lærling_info = assessment.get('krav_om_lærlinger', {})
        
        lines.extend([
            "## 5. Krav om lærlinger\n",
            f"**Status:** {'✅ Påkrevd' if lærling_info.get('status') else '❌ Ikke påkrevd'}",
            f"**Hjemmel:** Instruks punkt 6"
        ])
        
        if lærling_info.get('begrunnelse'):
            lines.append(f"\n**Vurdering:**")
            lines.append(f"> {lærling_info['begrunnelse']}")
        
        # Sjekkliste for lærlinger
        lines.extend([
            "\n### Kriterier for lærlingkrav:",
            f"- [{'x' if procurement.get('value', 0) > 1_300_000 else ' '}] Over statlig terskelverdi (1,3 MNOK)",
            f"- [{'x' if procurement.get('duration_months', 0) > 3 else ' '}] Varighet over 3 måneder",
            f"- [{'x' if procurement.get('category') in ['bygge', 'anlegg'] else ' '}] Utførende fagområde med behov for læreplasser"
        ])
        
        lines.append("\n---\n")
        
        # Seksjon 6: Aktsomhetsvurderinger
        aktsomhet = assessment.get('aktsomhetsvurdering_kravsett', 'Ikke påkrevd')
        
        lines.extend([
            "## 6. Aktsomhetsvurderinger for ansvarlig næringsliv\n",
            f"**Kravsett:** {aktsomhet}",
            f"**Hjemmel:** Instruks punkt 7"
        ])
        
        if aktsomhet != 'Ikke påkrevd':
            lines.extend([
                f"\n**Når gjelder {aktsomhet}:**",
                f"- Kravsett A: Alminnelige krav ved høy risiko",
                f"- Kravsett B: Forenklede krav (kort varighet eller umodent marked)"
            ])
        
        lines.append("\n---\n")
        
        # Seksjon 7: Anbefalinger
        recommendations = assessment.get('recommendations', [])
        
        if recommendations:
            lines.extend([
                "## 7. Anbefalinger\n"
            ])
            for rec in recommendations:
                lines.append(f"- {rec}")
            lines.append("")
        
        # Seksjon 8: Oppfølgingspunkter
        lines.extend([
            "## 8. Oppfølgingspunkter\n",
            "### Ved kontraktsinngåelse:",
            "- [ ] Verifiser at alle seriøsitetskrav er inkludert i kontrakten",
            "- [ ] Sikre at underleverandørbegrensninger er tydelig spesifisert",
            "- [ ] Inkluder sanksjonsbestemmelser ved brudd",
            "\n### Under kontraktsperioden:",
            "- [ ] Registrer i HMSREG hvis relevant",
            "- [ ] Gjennomfør risikobaserte kontroller",
            "- [ ] Følg opp mannskapslister og HMS-kort",
            "- [ ] Verifiser lærlingbruk hvis påkrevd",
            "\n---\n"
        ])
        
        # Metadata
        lines.extend([
            "## Metadata\n",
            f"- **Dokument ID:** {procurement.get('id', 'Ikke generert')}",
            f"- **Konfidensnivå:** {assessment.get('confidence', 0):.0%}",
            f"- **Genereringsverktøy:** Oslomodell Document Generator v1.0"
        ])
        
        # Hvis vi har kilder
        sources = assessment.get('sources_used', [])
        if sources:
            lines.extend([
                f"\n### Kilder brukt i vurdering:",
            ])
            for source in sources:
                lines.append(f"- {source}")
        
        lines.append("\n---")
        lines.append("\n*Dette dokumentet er automatisk generert basert på Oslomodell-vurdering og skal kvalitetssikres før bruk.*")
        
        return "\n".join(lines)
    
    def generate_summary_table(self, 
                              assessments: List[Dict[str, Any]]) -> str:
        """
        Genererer en oppsummeringstabell for flere anskaffelser.
        
        Args:
            assessments: Liste med vurderinger
            
        Returns:
            Markdown-tabell
        """
        lines = [
            "| Anskaffelse | Verdi (NOK) | Risiko | Antall krav | Underlev. | Lærlinger |",
            "|-------------|-------------|---------|-------------|-----------|-----------|"
        ]
        
        for a in assessments:
            proc = a.get('procurement', {})
            assess = a.get('assessment', {})
            
            name = proc.get('name', 'Ukjent')[:30]
            value = f"{proc.get('value', 0):,}"
            risk = assess.get('vurdert_risiko_for_akrim', 'N/A')
            krav_count = len(assess.get('påkrevde_seriøsitetskrav', []))
            underlev = assess.get('anbefalt_antall_underleverandørledd', 'N/A')
            lærling = "Ja" if assess.get('krav_om_lærlinger', {}).get('status') else "Nei"
            
            lines.append(f"| {name} | {value} | {risk} | {krav_count} | {underlev} | {lærling} |")
        
        return "\n".join(lines)


# Convenience functions
async def generate_from_orchestration(orchestration_context: Dict[str, Any], 
                                     output_dir: str = "generated_documents") -> str:
    """
    Genererer dokument direkte fra orchestrator context.
    
    Args:
        orchestration_context: Context fra ReasoningOrchestrator
        output_dir: Output directory
        
    Returns:
        Filepath to generated document
    """
    generator = OslomodellDocumentGenerator(output_dir)
    
    # Ekstraher data fra context
    procurement_data = None
    oslomodell_assessment = None
    
    # Finn procurement data
    if 'current_state' in orchestration_context:
        if 'request' in orchestration_context['current_state']:
            procurement_data = orchestration_context['current_state']['request']
    
    # Finn Oslomodell assessment
    for exec_entry in orchestration_context.get('execution_history', []):
        if exec_entry['action']['method'] == 'agent.run_oslomodell':
            if exec_entry['result'].get('status') == 'success':
                oslomodell_assessment = exec_entry['result']['result']
                break
    
    if not procurement_data or not oslomodell_assessment:
        raise ValueError("Could not extract required data from orchestration context")
    
    return generator.generate_document(procurement_data, oslomodell_assessment)


# Test function
if __name__ == "__main__":
    # Test med eksempeldata
    test_procurement = {
        "id": "test-123",
        "name": "Totalentreprise ny barnehage Majorstuen",
        "value": 35_000_000,
        "category": "bygge",
        "duration_months": 18,
        "description": "Bygging av ny 6-avdelings barnehage med uteområder"
    }
    
    test_assessment = {
        "vurdert_risiko_for_akrim": "høy",
        "påkrevde_seriøsitetskrav": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", 
                                     "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V"],
        "anbefalt_antall_underleverandørledd": 1,
        "aktsomhetsvurdering_kravsett": "A",
        "krav_om_lærlinger": {
            "status": True,
            "begrunnelse": "Over terskelverdi, varighet over 3 mnd, byggearbeid"
        },
        "recommendations": [
            "Gjennomfør grundig prekvalifisering av entreprenører",
            "Etabler rutiner for stedlig kontroll",
            "Bruk HMSREG aktivt i oppfølging"
        ],
        "confidence": 0.95,
        "sources_used": ["oslo-001", "oslo-002", "oslo-003"]
    }
    
    generator = OslomodellDocumentGenerator()
    filepath = generator.generate_document(test_procurement, test_assessment)
    print(f"✅ Test document generated: {filepath}")