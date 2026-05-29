import pdfplumber
import os

def read_pdf(path):
    print(f"\n--- {os.path.basename(path)} ---")
    if not os.path.exists(path):
        print("File does not exist")
        return
    with pdfplumber.open(path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            print(f"--- Page {idx+1} ---")
            print(text if text else "[No text]")

if __name__ == "__main__":
    read_pdf("data/investigation/479928034.pdf")
