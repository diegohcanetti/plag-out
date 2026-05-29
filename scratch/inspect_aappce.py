import pdfplumber
import os

def read_pdf(path):
    print(f"\n--- {os.path.basename(path)} ---")
    if not os.path.exists(path):
        print("File does not exist")
        return
    with pdfplumber.open(path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for idx in range(4, min(len(pdf.pages), 10)):
            page = pdf.pages[idx]
            text = page.extract_text()
            print(f"\n--- Page {idx+1} ---")
            print(text[:1500] if text else "[No text]")

if __name__ == "__main__":
    read_pdf("data/aappce_pdfs/Informe-10-Red-MIP-AAPPCE.pdf")
