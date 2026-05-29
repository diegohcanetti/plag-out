import pdfplumber
import re
import os

PEST_PATTERNS = {
    "Dalbulus maidis": ["dalbulus maidis", "chicharrita"],
    "Spodoptera frugiperda": ["spodoptera frugiperda", "cogollero"],
    "Helicoverpa gelotopoeon": ["helicoverpa gelotopoeon", "bolillera"],
    "Faronta albilinea": ["faronta albilinea", "desgranadora"],
    "Pseudaletia adultera": ["pseudaletia adultera", "militar"],
    "Diatraea saccharalis": ["diatraea saccharalis", "barrenador"],
    "Rachiplusia nu": ["rachiplusia nu", "medidora"],
    "Chrysodeixis includens": ["chrysodeixis includens", "falsa medidora"],
    "Helicoverpa zea": ["helicoverpa zea", "oruga de la espiga", "isoca de la espiga"]
}

# Hub mappings for geocoding the 12 Nodos
NODE_HUBS = {
    1: {"locality": "Las Lajitas", "province": "Salta"},
    2: {"locality": "Bandera", "province": "Santiago del Estero"},
    3: {"locality": "Gálvez", "province": "Santa Fe"},
    4: {"locality": "Jesus Maria", "province": "Córdoba"},
    5: {"locality": "San Francisco", "province": "Córdoba"},
    6: {"locality": "Paraná", "province": "Entre Ríos"},
    7: {"locality": "Cañada de Gómez", "province": "Santa Fe"},
    8: {"locality": "Venado Tuerto", "province": "Santa Fe"},
    9: {"locality": "Pergamino", "province": "Buenos Aires"},
    10: {"locality": "Pehuajó", "province": "Buenos Aires"},
    11: {"locality": "Bahía Blanca", "province": "Buenos Aires"},
    12: {"locality": "Tres Arroyos", "province": "Buenos Aires"}
}

def parse_v2_pdf(pdf_path):
    print(f"\nParsing {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        # Detect if it's V2 by looking at Page 5 or 6 for "REFERENCIAS"
        is_v2 = False
        ref_page_idx = -1
        for idx in range(3, min(len(pdf.pages), 8)):
            text = pdf.pages[idx].extract_text()
            if text and ("REFERENCIAS" in text.upper() or "RIESGO BAJO" in text.upper() or ("REFE" in text.upper() and "REN" in text.upper() and "CIAS" in text.upper())):
                is_v2 = True
                ref_page_idx = idx
                print(f"Detected V2 format! REFERENCIAS is at Page {idx+1}")
                break
        
        if not is_v2:
            print("Not V2 PDF")
            return
            
        # Parse consecutive pages starting from ref_page_idx + 1
        for node_id in range(1, 13):
            page_idx = ref_page_idx + node_id
            if page_idx >= len(pdf.pages):
                break
            
            page = pdf.pages[page_idx]
            text = page.extract_text()
            if not text:
                continue
                
            hub = NODE_HUBS[node_id]
            print(f"\n--- Node {node_id}: {hub['locality']} ({hub['province']}) (Page {page_idx+1}) ---")
            
            lines = text.split("\n")
            for line in lines:
                line_lower = line.lower()
                # Stop parsing if we reach the footer/comments section
                if any(k in line_lower for k in ["¿a qué prestar", "fecha", "coordina", "observaciones generales", "informe #", "auspician"]):
                    break
                    
                for pest, patterns in PEST_PATTERNS.items():
                    matched = False
                    for pat in patterns:
                        if pat in line_lower:
                            # Found the pest pattern! Now let's extract the severity (B, M, A)
                            # We look at the substring following the match
                            idx_pat = line_lower.find(pat)
                            sub = line[idx_pat + len(pat):].strip()
                            
                            # Match crops followed by B, M, or A
                            # Crop codes are 2-4 uppercase characters like SJ, MZ, PO, SRG, GR etc.
                            # Also allow them to be lowercase in the line just in case, but usually they are uppercase.
                            # The severity is the uppercase B, M, or A
                            match = re.search(r'\b(?:[A-Z]{2,4}\s+)*\b([BMA])\b', sub)
                            if match:
                                severity = match.group(1)
                                print(f"  Matched: '{pest}' -> Severity: {severity} (Line: '{line.strip()}')")
                                matched = True
                                break
                            else:
                                # Try a looser search if no uppercase crop code: look for the first B, M, or A in the rest of the line
                                match_loose = re.search(r'\b([BMA])\b', sub)
                                if match_loose:
                                    severity = match_loose.group(1)
                                    print(f"  Matched Loose: '{pest}' -> Severity: {severity} (Line: '{line.strip()}')")
                                    matched = True
                                    break

if __name__ == "__main__":
    pdf_dir = "data/aappce_pdfs"
    for f in sorted(os.listdir(pdf_dir)):
        if f.lower().endswith(".pdf"):
            path = os.path.join(pdf_dir, f)
            try:
                parse_v2_pdf(path)
            except Exception as e:
                print(f"Error parsing {f}: {e}")
