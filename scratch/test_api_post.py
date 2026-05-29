import requests
import json

url = "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/_procesar_mapa.php"

# Let's request Presence (presencia_maleza) of Chicharrita in Maiz Temprano/Tardio for all years
payload = {
    "accion": "procesar_form",
    "tipo_mapa": "presencia_maleza",
    "filtros_malezas[]": ["maiz-temprano", "maiz-tardio"],
    "malezas[]": ["chicharrita-en-maiz-temprano", "chicharrita-en-maiz-tardio"],
    "anosPM[]": ["2023/2024", "2021/2022", "2019/2020"]
}

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.aapresid.org.ar",
    "Referer": "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/"
}

print("Posting to AAPRESID API endpoint...")
# We must use urlencoded data. Since there are list inputs like 'malezas[]', 
# we can format the request body as a string or pass multiple key-value tuples/dict.
# Let's do urlencoded form formatting manually to make sure it's 100% correct.
data_tuples = [
    ("accion", "procesar_form"),
    ("tipo_mapa", "presencia_maleza"),
    ("filtros_malezas[]", "maiz-temprano"),
    ("filtros_malezas[]", "maiz-tardio"),
    ("malezas[]", "chicharrita-en-maiz-temprano"),
    ("malezas[]", "chicharrita-en-maiz-tardio"),
    ("anosPM[]", "2023/2024"),
    ("anosPM[]", "2021/2022"),
    ("anosPM[]", "2019/2020")
]

res = requests.post(url, data=data_tuples, headers=headers)
print("Status:", res.status_code)
try:
    data = res.json()
    print("Success! JSON Keys:", list(data.keys()))
    
    # Save a sample to scratch/sample_response.json
    with open("scratch/sample_response.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Saved sample response to scratch/sample_response.json")
    
    # Print some info about the response structure
    if "aDeptoMalezas" in data:
        deptos = data["aDeptoMalezas"]
        print(f"Number of departments in aDeptoMalezas: {len(deptos)}")
        # Print first few elements
        first_keys = list(deptos.keys())[:5]
        print("First few department keys:", first_keys)
        for k in first_keys:
            print(f"- Dept {k}: {deptos[k]}")
            
    if "aDeptoMediciones" in data:
        meds = data["aDeptoMediciones"]
        print(f"Number of elements in aDeptoMediciones: {len(meds)}")
        # Print first few elements
        first_keys = list(meds.keys())[:5]
        print("First few measurement keys:", first_keys)
        for k in first_keys:
            print(f"- Med {k}: {meds[k]}")
            
except Exception as e:
    print("Error parsing JSON:", e)
    print("Response text excerpt (first 500 chars):", res.text[:500])
