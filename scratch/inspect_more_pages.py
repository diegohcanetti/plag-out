import pdfplumber

with pdfplumber.open("data/aappce_pdfs/Informe-10-Red-MIP-AAPPCE.pdf") as pdf:
    for idx in range(10, len(pdf.pages)):
        text = pdf.pages[idx].extract_text()
        first_line = ""
        if text:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            first_line = " | ".join(lines[:4])
        print(f"Page {idx+1}: {first_line[:200]}")
