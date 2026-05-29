import pdfplumber

def inspect_page6_headers():
    path = "scratch/aappce_dec_2025.pdf"
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[5] # Page 6
        print("=== PAGE 6 TEXT COORDS ===")
        for word in page.extract_words():
            if word["top"] < 180:
                print(f"Text='{word['text']}', x0={word['x0']:.1f}, top={word['top']:.1f}")

if __name__ == "__main__":
    inspect_page6_headers()
