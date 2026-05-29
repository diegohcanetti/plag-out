import pdfplumber

def inspect_details():
    path = "scratch/aappce_dec_2025.pdf"
    with pdfplumber.open(path) as pdf:
        for page_num in [5, 6]:
            print(f"\n--- Page {page_num} Details ---")
            page = pdf.pages[page_num - 1]
            text = page.extract_text()
            if text:
                for line in text.split("\n"):
                    print(line)

if __name__ == "__main__":
    inspect_details()
