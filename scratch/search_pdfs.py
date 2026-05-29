import pdfplumber
import os

def search_pdf(path, keyword):
    print(f"\nSearching for '{keyword}' in {os.path.basename(path)}:")
    if not os.path.exists(path):
        print("File does not exist")
        return
    with pdfplumber.open(path) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and keyword.lower() in text.lower():
                print(f"--- Page {idx+1} ---")
                lines = text.split("\n")
                for line in lines:
                    if keyword.lower() in line.lower():
                        print(f"  {line}")

if __name__ == "__main__":
    search_pdf("data/investigation/479928034.pdf", "aappce")
    search_pdf("data/investigation/479928034.pdf", "bulletin")
    search_pdf("data/investigation/479928034.pdf", "plaga")
    search_pdf("data/investigation/Proyecto Plag-out_ Búsqueda de Datos.pdf", "aappce")
