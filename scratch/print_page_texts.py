import pdfplumber

with pdfplumber.open("data/aappce_pdfs/Informe-10-Red-MIP-AAPPCE.pdf") as pdf:
    for idx in range(3, 8):
        text = pdf.pages[idx].extract_text()
        print(f"--- Page {idx+1} ---")
        print(text if text else "[No text]")
