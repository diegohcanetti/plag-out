import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_autocomplete():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    url = "https://www.sinavimo.gob.ar/ac-plagas?q=Dalbulus"
    print(f"Fetching autocomplete: {url}")
    res = session.get(url, verify=False)
    print(f"Status: {res.status_code}")
    print("Response text:", res.text)
    
    url2 = "https://www.sinavimo.gob.ar/ac-plagas?q=Spodoptera"
    print(f"Fetching autocomplete 2: {url2}")
    res2 = session.get(url2, verify=False)
    print(f"Status 2: {res2.status_code}")
    print("Response text 2:", res2.text)

if __name__ == "__main__":
    test_autocomplete()
