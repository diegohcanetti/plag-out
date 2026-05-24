import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def inspect_profile():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    url = "https://www.sinavimo.gob.ar/plaga/dalbulus-maidis"
    print(f"Fetching profile page: {url}")
    res = session.get(url, verify=False)
    
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Let's save the HTML to scratch/sinavimo_profile.html for manual inspection if needed
    with open('scratch/sinavimo_profile.html', 'w', encoding='utf-8') as f:
        f.write(res.text)
    
    print("Page Title:", soup.title.text if soup.title else "None")
    
    # Find headers, sections, tables, divs
    # Let's look for sections with common keywords
    print("\n--- Level 2 Headers ---")
    for h2 in soup.find_all('h2'):
        print(f"H2: {h2.text.strip()}")
        
    print("\n--- Level 3 Headers ---")
    for h3 in soup.find_all('h3'):
        print(f"H3: {h3.text.strip()}")
        
    # Check if there is a table or lists of provinces
    tables = soup.find_all('table')
    print(f"\nFound {len(tables)} tables on page.")
    for i, table in enumerate(tables):
        print(f"\nTable {i+1} headers:")
        headers = [th.text.strip() for th in table.find_all('th')]
        print(headers)
        
        # Print first few rows
        rows = table.find_all('tr')
        print(f"Table has {len(rows)} rows.")
        for row in rows[:5]:
            cells = [td.text.strip() for td in row.find_all('td')]
            if cells:
                print("  Row:", cells)

if __name__ == "__main__":
    inspect_profile()
