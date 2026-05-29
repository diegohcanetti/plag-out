import pdfplumber

def inspect_headers():
    path = "scratch/aappce_dec_2025.pdf"
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[4] # Page 5
        print("=== TEXT COORDS ===")
        # Print text and its bounding box for words containing specific parts
        for word in page.extract_words():
            text = word["text"]
            # Print words in the top section
            if word["top"] < 180:
                print(f"Text='{text}', x0={word['x0']:.1f}, x1={word['x1']:.1f}, top={word['top']:.1f}")

if __name__ == "__main__":
    inspect_headers()
