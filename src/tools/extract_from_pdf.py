# extract_pdf.py - Python-skript for å trekke ut krav fra PDF
import re
from pathlib import Path
from pypdf import PdfReader

def extract_requirement_by_code(pdf_path: str, requirement_code: str) -> str:
    """
    Trekker ut teksten for et spesifikt krav fra en PDF-fil.

    Args:
        pdf_path: Stien til PDF-filen.
        requirement_code: Kravkoden å søke etter (f.eks. "A", "B").

    Returns:
        Teksten som tilhører det spesifikke kravet, eller en feilmelding.
    """
    try:
        # Konkrete valg for dokumentet som skal leses
        pdf_file = PdfReader(pdf_path)

        # Markøren som deler opp seksjonene
        # Merk: Markøren må tilpasses formatet i dokumentet. I dette tilfellet er det "A)", "B)", etc.
        # Vi bruker en regulær uttrykksmønster for å fange kravkoden.
        start_marker = re.compile(rf'^{re.escape(requirement_code)}\s*\)')

        # Markører for alle seksjoner i dokumentet, inkludert seriøsitetskrav og aktsomhetsvurderinger
        all_markers = [
            'A)', 'B)', 'C)', 'D)', 'E)', 'F)', 'G)', 'H)', 'I)', 'J)', 'K)', 'L)', 'M)', 'N)', 'O)', 'P)', 'Q)', 'R)', 'S)', 'T)', 'U)', 'V)',
            '3.1.1', '3.1.2', '3.2.1', '3.2.2'
        ]
        
        # Sorter markørene for å sikre at vi kan finne den neste markøren i rekkefølge
        # Vi lager en ordbok for raskt oppslag av den neste markøren
        marker_order = {marker: next_marker for marker, next_marker in zip(all_markers, all_markers[1:] + [None])}

        # Finn start- og sluttmarkørene for det forespurte kravet
        start_pattern = re.compile(rf'^{re.escape(requirement_code)}\s*\)')
        end_marker = marker_order.get(requirement_code)

        if not end_marker:
            # Hvis det ikke finnes en neste markør, kan vi anta at det er den siste seksjonen.
            # Dette krever en annen logikk for å fange opp resten av teksten.
            end_pattern = None
        else:
            end_pattern = re.compile(rf'^{re.escape(end_marker)}\s*\)')
        
        # Ekstraksjon av teksten
        extracted_text = ""
        in_section = False
        
        for page in pdf_file.pages:
            page_text = page.extract_text()
            lines = page_text.split('\n')
            
            for line in lines:
                # Sjekk om vi skal starte å samle tekst
                if start_pattern.match(line.strip()) and not in_section:
                    in_section = True
                    extracted_text += line.strip() + '\n'
                    continue
                
                # Sjekk om vi skal slutte å samle tekst
                if in_section:
                    # Sjekk om linjen er den neste markøren
                    if end_pattern and end_pattern.match(line.strip()):
                        return extracted_text.strip()
                    # Legg til linjen i den ekstraherte teksten
                    extracted_text += line + '\n'

        if in_section:
            return extracted_text.strip()

        return f"Krav med kode '{requirement_code}' ble ikke funnet."

    except FileNotFoundError:
        return f"Feil: Filen '{pdf_path}' ble ikke funnet."
    except Exception as e:
        return f"En feil oppstod: {e}"

# --- Bruk av skriptet ---
if __name__ == '__main__':
    # Angi stien til PDF-filen
    file_name = "Krav oslomodellen.pdf"
    
    # Eksempel på å trekke ut krav A
    krav_a_tekst = extract_requirement_by_code(file_name, "A")
    print(f"--- Innhold for Krav A ---")
    print(krav_a_tekst)
    print("\n" + "="*50 + "\n")
    
    # Eksempel på å trekke ut krav V
    krav_v_tekst = extract_requirement_by_code(file_name, "V")
    print(f"--- Innhold for Krav V ---")
    print(krav_v_tekst)
    print("\n" + "="*50 + "\n")

    # Eksempel på å trekke ut Kravsett B
    kravsett_b_tekst = extract_requirement_by_code(file_name, "3.2")
    print(f"--- Innhold for Kravsett B ---")
    print(kravsett_b_tekst)
    print("\n" + "="*50 + "\n")