import pdfplumber

with pdfplumber.open("data/aappce_pdfs/Informe-10-Red-MIP-AAPPCE.pdf") as pdf:
    print(pdf.pages[6].extract_text()[:600])
