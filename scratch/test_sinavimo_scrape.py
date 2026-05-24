import requests
from bs4 import BeautifulSoup
import urllib3

# Disable insecure request warnings if any
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_sinavimo():
    session = requests.Session()
    # Add a real-looking user agent
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    # 1. Fetch the main page to get form tokens
    url = "https://www.sinavimo.gob.ar/base-fitosanitarios"
    print(f"Fetching base page: {url}")
    res = session.get(url, verify=False)
    if res.status_code != 200:
        print(f"Failed to fetch base page, status: {res.status_code}")
        return
        
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Find form_build_id
    form_build_id_input = soup.find('input', {'name': 'form_build_id'})
    if not form_build_id_input:
        print("Could not find form_build_id in page!")
        return
    form_build_id = form_build_id_input.get('value')
    print(f"Found form_build_id: {form_build_id}")
    
    # 2. Submit the search form
    payload = {
        'plaga': 'Dalbulus maidis',
        'form_build_id': form_build_id,
        'form_id': 'ac_plagas_form',
        'buscar': 'Buscar'
    }
    
    print("Submitting search for Dalbulus maidis...")
    res_search = session.post(url, data=payload, verify=False)
    print(f"Search response status: {res_search.status_code}")
    
    # Let's save the response content to see what it returned
    soup_result = BeautifulSoup(res_search.text, 'html.parser')
    
    # Print the page title or search results container
    print("Page Title of Results:", soup_result.title.text if soup_result.title else "None")
    
    # Look for lists or links related to plagas
    plaga_links = []
    for a in soup_result.find_all('a', href=True):
        if '/plaga/' in a['href']:
            plaga_links.append((a.text.strip(), a['href']))
            
    print(f"Found {len(plaga_links)} plaga links in search results:")
    for name, href in plaga_links:
        print(f"- {name}: {href}")
        
    # Let's write the result HTML to a scratch file to inspect if needed
    with open('scratch/sinavimo_search_results.html', 'w', encoding='utf-8') as f:
        f.write(res_search.text)
    print("Saved results to scratch/sinavimo_search_results.html")

if __name__ == "__main__":
    test_sinavimo()
