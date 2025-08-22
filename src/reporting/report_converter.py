# src/reporting/report_converter.py
import pypandoc
import structlog
from typing import Optional

logger = structlog.get_logger()

class ReportConverter:
    """
    Konverterer en rapport (gitt som Markdown-streng) til andre formater
    som DOCX (Word) og PDF ved hjelp av Pandoc.
    """

    def to_docx(self, markdown_text: str, output_path: str, reference_docx: Optional[str] = None):
        """
        Konverterer Markdown-tekst til en Word-fil (.docx).

        Args:
            markdown_text: Innholdet som skal konverteres.
            output_path: Stien til den ferdige Word-filen (f.eks. "rapport.docx").
            reference_docx: Valgfri sti til en Word-malfil (.docx) for å styre stiler.
        """
        log = logger.bind(format="docx", output=output_path)
        log.info("starting_docx_conversion")
        
        extra_args = []
        if reference_docx:
            log.info("using_reference_docx", template=reference_docx)
            extra_args.extend(['--reference-doc', reference_docx])
        
        try:
            pypandoc.convert_text(
                markdown_text,
                'docx',
                format='markdown',
                outputfile=output_path,
                extra_args=extra_args
            )
            log.info("docx_conversion_successful")
        except OSError as e:
            log.error("pandoc_not_found", error=str(e), msg="Pandoc er sannsynligvis ikke installert eller ikke i systemets PATH.")
        except Exception as e:
            log.error("docx_conversion_failed", error=str(e))
            
    def to_pdf(self, markdown_text: str, output_path: str, font: str = "Calibri"):
        """
        Konverterer Markdown-tekst til en PDF-fil med en spesifikk systemskrift.
        Krever at en LaTeX-motor (f.eks. TinyTeX) og 'xelatex' er installert.
        """
        log = logger.bind(format="pdf", output=output_path, font=font)
        log.info("starting_pdf_conversion")

        try:
            pypandoc.convert_text(
                markdown_text,
                'pdf',
                format='markdown',
                outputfile=output_path,
                # <--- ENDRING: Nye argumenter for å styre skrift ---
                extra_args=[
                    '--pdf-engine=xelatex',     # Bytt til en motor som kan bruke systemskrifter
                    f'-V', f'mainfont={font}',   # Sett hovedskriften for dokumentet
                    '-V', 'fontsize=11pt'       # Valgfritt: Sett skriftstørrelse
                ]
            )
            log.info("pdf_conversion_successful")
        except OSError as e:
            log.error("pandoc_or_latex_not_found", error=str(e), msg="Pandoc og/eller en LaTeX-motor (som TinyTeX med xelatex) er sannsynligvis ikke installert.")
        except Exception as e:
            log.error("pdf_conversion_failed", error=str(e))