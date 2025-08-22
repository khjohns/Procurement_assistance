# src/reporting/protocol_generator.py
import yaml
from typing import Dict, Any, List, Set

from src.models.base_models import BaseProcurementInput, BaseAssessment, Requirement, Rule

class ProtocolGenerator:
    """
    Konverterer et datrikt BaseAssessment-objekt til en brukervennlig
    og lesbar rapport i Markdown-format, styrt av en konfigurasjonsfil.
    """

    def __init__(self, config_path: str):
        """Laster konfigurasjonen som styrer rapportens layout og innhold."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            raise IOError(f"Protokoll-konfigurasjonsfil ikke funnet: {config_path}")
        
        self.titles = self.config.get('protocol_titles', {})
        self.groups = self.config.get('requirement_groups', {})
        self.explanations = self.config.get('requirement_explanations', {})

    def generate(self, assessment: BaseAssessment, procurement: BaseProcurementInput) -> str:
        """Hovedmetode som bygger hele rapporten."""
        
        # Grupper kravene for enklere behandling
        applicable_codes = {req.code for req in assessment.applicable_requirements}
        grouped_reqs = self._group_requirements(assessment.applicable_requirements)

        report_parts = []
        
        # --- NYTT STEG: Bygg metadata-seksjonen FØRST ---
        report_parts.append(self._build_metadata_section(procurement))
        # -----------------------------------------------

        for section in self.config.get('section_order', []):
            if section == 'summary':
                report_parts.append(self._build_summary_section(assessment, applicable_codes))
            elif section == 'key_requirements':
                report_parts.append(self._build_key_requirements_section(grouped_reqs, assessment.triggered_rules))
            elif section == 'appendix':
                report_parts.append(self._build_appendix_section(grouped_reqs))

        report_parts.append(f"\n---\n*{self.titles.get('footer_text', '')}*")
        
        return "\n\n".join(report_parts)

    def _build_metadata_section(self, procurement: BaseProcurementInput) -> str:
        """Bygger en komplett og brukervennlig metadata-seksjon ved hjelp av en tabell."""
        
        # Hent og formater verdier med fallbacks og korrekt norsk formatering
        saksbehandler = procurement.requested_by or "Ikke oppgitt"
        saksnr = procurement.case_number or "Ikke oppgitt"
        prosjektnr = procurement.project_number or "Ikke oppgitt"
        tilbudsfrist = procurement.tender_deadline.strftime('%d.%m.%Y') if procurement.tender_deadline else "Ikke oppgitt"
        
        verdi_str = f"{procurement.value:,}".replace(',', ' ') + " NOK" if procurement.value is not None else "Ikke oppgitt"
        varighet_str = f"{procurement.duration_months} måneder" if procurement.duration_months is not None else "Ikke oppgitt"
        
        category_str = procurement.category.value.title() if procurement.category else "Ikke oppgitt"
        subcategory_str = procurement.subcategory.value.replace('_', ' ').title() if procurement.subcategory else "Ikke spesifisert"

        beskrivelse = procurement.description or "Ingen beskrivelse oppgitt."
        
        # Bygg rapport-delen. Vi bruker en kombinasjon av vanlig tekst og en tabell for det beste resultatet.
        parts = [
            f"# {self.titles.get('main_title', 'VURDERINGS-RAPPORT')}",
            # Enkeltstående informasjon plasseres utenfor tabellen
            f"\n**Anskaffelsen gjelder:** {procurement.name}",
            
            # Overskriften for seksjonen
            f"\n### {self.titles.get('metadata_section_title', '1. Opplysninger om anskaffelsen')}",
            
            # En tabell for parvis data. Dette sikrer perfekt justering.
            # Headeren er nødvendig for Markdown, men innholdet kan være tomt.
            "| | | | |",
            "|:---|:---|:---|:---|",
            f"| **Saksbehandler:** | {saksbehandler} | **Saksnr.:** | {saksnr} |",
            f"| **Kategori:** | {category_str} | **Underkategori:** | {subcategory_str} |",
            f"| **Anslått verdi (eks. mva):** | {verdi_str} | **Prosjektnr.:** | {prosjektnr} |",
            f"| **Kontraktens varighet:** | {varighet_str} | **Tilbudsfrist:** | {tilbudsfrist} |",

            # Beskrivelsen plasseres pent under tabellen
            "\n**Kort om behovet:**",
            f": {beskrivelse}"
        ]
        
        return "\n".join(parts)

    def _build_summary_section(self, assessment: BaseAssessment, codes: Set[str]) -> str:
        """Bygger sammendragsseksjonen."""
        parts = [
            f"### {self.titles.get('summary_section_title', '2. Hovedkonklusjoner')}",
            f"Agent-vurderingen har identifisert **{len(assessment.applicable_requirements)}** anvendelige krav for denne anskaffelsen."
        ]
        
        # Legg til spesifikke høydepunkter
        if 'V' in codes:
            parts.append("- **Krav om lærlinger gjelder.**")
        if 'RESERVERT-KONTRAKT-PLIKT' in codes:
            parts.append("- **Plikt til reservert kontrakt gjelder.** Konkurransen må forbeholdes.")
        if 'AKTSOMHET-A' in codes or 'AKTSOMHET-B' in codes:
            parts.append("- **Krav til aktsomhetsvurderinger gjelder.**")
        
        # Inkluder anbefalinger og advarsler
        if assessment.recommendations or assessment.warnings:
            parts.append(f"\n### {self.titles.get('recommendations_title', 'Anbefalinger og Advarsler')}")
            for rec in assessment.recommendations:
                parts.append(f"- **Anbefaling:** {rec}")
            for warn in assessment.warnings:
                 parts.append(f"- **Advarsel:** {warn}")

        return "\n".join(parts)

    def _group_requirements(self, requirements: List[Requirement]) -> Dict[str, List[Requirement]]:
        """Grupperer en flat liste med krav basert på gruppene definert i config."""
        grouped = {group_name: [] for group_name in self.groups}
        other_reqs = []
        accounted_for_codes = set()

        # Legg krav i sine forhåndsdefinerte grupper
        for group_name, codes in self.groups.items():
            for req in requirements:
                if req.code in codes:
                    grouped[group_name].append(req)
                    accounted_for_codes.add(req.code)

        # Samle krav som ikke passet i noen gruppe
        for req in requirements:
            if req.code not in accounted_for_codes:
                other_reqs.append(req)
        
        if other_reqs:
            grouped["Andre krav"] = other_reqs
            
        # Fjern tomme grupper
        return {name: reqs for name, reqs in grouped.items() if reqs}
    
    def _format_code_range(self, reqs: List[Requirement]) -> str:
        """Formaterer en liste med kravkoder til en kompakt streng, f.eks. 'A-E, G'."""
        codes = sorted([r.code for r in reqs if len(r.code) == 1]) # Gjelder kun for enkeltbokstaver
        
        if not codes:
            # For sammensatte koder, bare list dem opp
            return ", ".join(sorted([r.code for r in reqs]))

        ranges = []
        start = end = codes[0]
        
        for i in range(1, len(codes)):
            if ord(codes[i]) == ord(end) + 1:
                end = codes[i]
            else:
                ranges.append(f"{start}-{end}" if start != end else start)
                start = end = codes[i]
        ranges.append(f"{start}-{end}" if start != end else start)
        
        # Legg til ikke-bokstavkoder til slutt
        non_alpha_codes = sorted([r.code for r in reqs if len(r.code) > 1])
        final_list = ranges + non_alpha_codes
        
        return ", ".join(final_list)

    def _build_key_requirements_section(self, grouped_reqs: Dict[str, List[Requirement]], all_rules: List[Rule]) -> str:
        """Bygger den kompakte tabell-oversikten over krav med presise kildehenvisninger."""
        parts = [f"## {self.titles.get('key_requirements_section_title', '3. Oversikt over krav')}"]
        
        table = [
            "| Kravområde | Relevante Kravkoder | Kildehenvisning |",
            "|:---|:---|:---|"
        ]

        # Hent de brukervennlige navnene fra konfigurasjonen
        source_names_map = self.titles.get('source_document_names', {})
        
        # Lag en mapping fra kravkode til den mest spesifikke referansen fra den utløste regelen.
        rule_ref_map = {}
        for rule in all_rules:
            if rule.justification_reference:
                for code in rule.activates_requirement_codes:
                    if code not in rule_ref_map: # Bare ta den første (høyest prioriterte)
                        rule_ref_map[code] = rule.justification_reference

        for group_name, reqs in grouped_reqs.items():
            if not reqs:
                continue
            
            code_summary = self._format_code_range(reqs)

            # --- FORBEDRET LOGIKK FOR KILDEHENVISNING ---
            sources = set()
            for req in reqs:
                # Legg til spesialhåndtering for skatteattest ---
                if req.code == "SKATT-STD":
                    sources.add("Anskaffelsesforskriften (§ 7-2)")
                    continue # Gå til neste krav
                elif req.code == "SKATT-UTV":
                    sources.add("Instruks for Oslo kommunes anskaffelser (Krav T)")
                    continue
                # Prioritet 1: Bruk den spesifikke referansen fra regelen hvis den finnes.
                specific_ref = rule_ref_map.get(req.code)
                if specific_ref:
                    # Hvis referansen allerede inneholder dokumentnavnet, bruk den direkte.
                    if any(name.lower() in specific_ref.lower() for name in source_names_map.values()):
                         sources.add(specific_ref)
                    else: # Hvis ikke, kombiner med dokumentnavnet.
                        doc_name = source_names_map.get(req.source.value, req.source.value.replace('_', ' ').title())
                        sources.add(f"{doc_name} ({specific_ref})")
                else:
                    # Prioritet 2 (Fallback): Bruk det generelle, brukervennlige navnet fra config.
                    doc_name = source_names_map.get(req.source.value, req.source.value.replace('_', ' ').title())
                    sources.add(doc_name)
            
            source_str = "; ".join(sorted(list(sources)))
            # --- SLUTT FORBEDRING ---

            table.append(f"| {group_name} | `{code_summary}` | {source_str} |")

        parts.append("\n".join(table))
        return "\n".join(parts)
        
    def _build_appendix_section(self, grouped_reqs: Dict[str, List[Requirement]]) -> str:
        """Bygger vedlegget med detaljerte kravforklaringer."""
        parts = [f"## {self.titles.get('appendix_section_title', 'Vedlegg')}"]

        for group_name, reqs in grouped_reqs.items():
            if not reqs:
                continue
            
            parts.append(f"\n### {group_name}")
            for req in sorted(reqs, key=lambda r: r.code):
                explanation = self.explanations.get(req.code, req.description or "Ingen detaljert forklaring tilgjengelig.")
                parts.append(f"- **[{req.code}] {req.name}:** {explanation}")

        return "\n".join(parts)