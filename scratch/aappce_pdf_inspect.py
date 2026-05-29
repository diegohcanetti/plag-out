import requests
import pdfplumber
import os

def download_and_inspect():
    pdf_url = "https://aappce.org/wp-content/uploads/2025/12/Red-MIP-AAPPCE-Monitoreo-Nacional-Diciembre-2025_VF-1.pdf"
    local_path = "scratch/aappce_dec_2025.pdf"
    os.makedirs("scratch", exist_ok=True)
    
    print(f"Downloading {pdf_url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    res = requests.get(pdf_url, headers=headers, verify=False, timeout=20)
    with open(local_path, "wb") as f:
        f.write(res.content)
    print("Downloaded!")
    
    print("\nParsing PDF:")
    with pdfplumber.open(local_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            print(f"\n--- Page {idx+1} ---")
            if text:
                # Print lines containing plagues or counts or tables
                lines = text.split("\n")
                print(f"Total lines: {len(lines)}")
                for line in lines[:30]: # print first 30 lines of each page
                    print("  ", line)
            else:
                print("  [No text extracted]")

if __name__ == "__main__":
    download_and_inspect()
