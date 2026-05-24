import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_sinavimo_exact():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    url = "https://www.sinavimo.gob.ar/base-fitosanitarios"
    res = session.get(url, verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    form_build_id = soup.find('input', {'name': 'form_build_id'}).get('value')
    
    # Let's try submitting 'Dalbulus maidis (9538)'
    payload = {
        'plaga': 'Dalbulus maidis (9538)',
        'form_build_id': form_build_id,
        'form_id': 'ac_plagas_form',
        'buscar': 'Buscar'
    }
    
    print("Submitting exact name for Dalbulus maidis...")
    res_search = session.post(url, data=payload, verify=False)
    print(f"Status: {res_search.status_code}")
    print(f"Final URL: {res_search.url}")
    
    soup_result = BeautifulSoup(res_search.text, 'html.parser')
    print("Page Title:", soup_result.title.text if soup_result.title else "None")
    
    # Let's see if we landed directly on the plaga page or if there's a specific link
    plaga_links = []
    for a in soup_result.find_all('a', href=True):
        if '/plaga/' in a['href']:
            plaga_links.append((a.text.strip(), a['href']))
            
    print(f"Found {len(plaga_links)} links in search results:")
    for name, href in plaga_links:
        print(f"- {name}: {href}")

if __name__ == "__main__":
    test_sinavimo_exact()
