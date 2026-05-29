import requests
from bs4 import BeautifulSoup

def inspect_aappce():
    # Try both possible spelling in case of subtle typos
    urls = [
        "https://aappce.org/informes_redmip/",
        "https://aappce.org/informes-redmip/"
    ]
    for url in urls:
        print(f"\nRequesting: {url}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            res = requests.get(url, headers=headers, verify=False, timeout=15)
            print(f"Status Code: {res.status_code}")
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                links = soup.find_all('a')
                print(f"Total links found: {len(links)}")
                pdf_links = [l.get('href') for l in links if l.get('href') and '.pdf' in l.get('href').lower()]
                print(f"PDF links found ({len(pdf_links)}):")
                for pl in pdf_links[:10]:
                    print("  ", pl)
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    inspect_aappce()
