import requests
import json

url = "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/_procesar_mapa.php"

# Let's request Abundance (abundancia_maleza) of Chicharrita in Maiz Tardio for all years
payload = {
    "accion": "procesar_form",
    "tipo_mapa": "abundancia_maleza",
    "cultivoMapaAbundancia[]": ["maiz-tardio"],
    "maleza[]": "chicharrita-en-maiz-tardio",
    "anosMapaAbundancia[]": ["2023/2024", "2021/2022", "2019/2020"]
}

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.aapresid.org.ar",
    "Referer": "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/"
}

print("Posting to AAPRESID API endpoint for Abundancia...")
data_tuples = [
    ("accion", "procesar_form"),
    ("tipo_mapa", "abundancia_maleza"),
    ("cultivoMapaAbundancia[]", "maiz-tardio"),
    ("maleza[]", "chicharrita-en-maiz-tardio"),
    ("anosMapaAbundancia[]", "2023/2024"),
    ("anosMapaAbundancia[]", "2021/2022"),
    ("anosMapaAbundancia[]", "2019/2020")
]

res = requests.post(url, data=data_tuples, headers=headers)
print("Status:", res.status_code)
try:
    data = res.json()
    print("Success! JSON Keys:", list(data.keys()))
    
    # Save a sample to scratch/sample_abundance_response.json
    with open("scratch/sample_abundance_response.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Saved sample response to scratch/sample_abundance_response.json")
    
    if "aDeptoMalezas" in data:
        deptos = data["aDeptoMalezas"]
        print(f"Number of departments in aDeptoMalezas: {len(deptos)}")
        first_keys = list(deptos.keys())[:5]
        for k in first_keys:
            print(f"- Dept {k}: {deptos[k]}")
            
except Exception as e:
    print("Error parsing JSON:", e)
    print("Response text excerpt (first 500 chars):", res.text[:500])
