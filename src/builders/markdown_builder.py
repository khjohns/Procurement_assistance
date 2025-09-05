# src/builders/markdown_builder.py
import yaml

class MarkdownBuilder:
    """
    Hjelpeklasse for å bygge Markdown med konsistent formatering.
    Løser alle whitespace- og formateringsproblemer.
    """
    
    def __init__(self):
        self.content = []
        self.config = self._load_formatting_config()
    
    def _load_formatting_config(self):
        """Laster formateringsregler fra config."""
        with open('config/procurement_note_structure.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)['formatting']
    
    def add_heading(self, text: str, level: int = 1) -> 'MarkdownBuilder':
        """Legger til overskrift med riktig antall linjeskift."""
        prefix = '#' * level
        self.content.append(f"{prefix} {text}")
        self.add_line_breaks(self.config['line_breaks_after_heading'])
        return self
    
    def add_paragraph(self, text: str) -> 'MarkdownBuilder':
        """Legger til et avsnitt."""
        self.content.append(text)
        self.add_line_breaks(1)
        return self

    def add_text_line(self, text: str) -> 'MarkdownBuilder':
        """Legger til en enkel tekstlinje uten ekstra linjeskift etterpå."""
        self.content.append(text)
        return self
    
    def add_line_breaks(self, count: int = 1) -> 'MarkdownBuilder':
        """Legger til spesifikt antall linjeskift."""
        for _ in range(count):
            self.content.append("")
        return self
    
    def add_list(self, items: list, style: str = None, tight: bool = False) -> 'MarkdownBuilder':
        """Legger til en liste med konsistent formatering."""
        style = style or self.config['list_style']
        for item in items:
            self.content.append(f"{style}{item}")
        
        # Kun legg til linjeskift hvis listen ikke skal være "tett"
        if not tight:
            self.add_line_breaks(1)
        return self
    
    def add_checklist(self, items: list, tight: bool = False) -> 'MarkdownBuilder':
        """Legger til sjekkliste."""
        style = self.config['checklist_style']
        for item in items:
            if isinstance(item, dict):
                text = item.get('text', '')
                checked = item.get('checked', False)
                check = 'x' if checked else ' '
                self.content.append(f"- [{check}] {text}")
            else:
                self.content.append(f"{style}{item}")
        if not tight:
            self.add_line_breaks(1)
        return self

    def add_nested_checklist_item(self, title: str, sub_items: list) -> 'MarkdownBuilder':
        """Legger til et sjekklistepunkt med en tett, innrykket underliste."""
        self.add_text_line(f"- [ ] {title}")
        for item in sub_items:
            self.add_text_line(f"  - {item}")
        return self
    
    def add_table(self, headers: list, rows: list) -> 'MarkdownBuilder':
        """Legger til tabell med korrekt formatering."""
        # Headers
        self.content.append("| " + " | ".join(headers) + " |")
        # Separator
        self.content.append("|" + "|".join(["---" for _ in headers]) + "|")
        # Rows
        for row in rows:
            self.content.append("| " + " | ".join(str(cell) for cell in row) + " |")
        self.add_line_breaks(1)
        return self
    
    def add_horizontal_rule(self) -> 'MarkdownBuilder':
        """Legger til horisontal linje."""
        self.content.append("---")
        return self
    
    def add_bold(self, text: str) -> str:
        """Returnerer tekst i bold."""
        return f"**{text}**"
    
    def add_italic(self, text: str) -> str:
        """Returnerer tekst i kursiv."""
        return f"*{text}*"
    
    def add_link(self, text: str, url: str) -> str:
        """Returnerer lenke."""
        return f"[{text}]({url})"
    
    def build(self) -> str:
        """Returnerer ferdig Markdown-dokument."""
        return "\n".join(self.content)
