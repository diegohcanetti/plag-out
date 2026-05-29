import requests

url = "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/js/mapasMalezas/jsMapa.js?v2024-11-v02"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
js_text = requests.get(url, headers=headers).text

# Find "function getResultMapa" and extract its block
idx = js_text.find("function getResultMapa")
if idx != -1:
    print("Found function getResultMapa at char:", idx)
    # Let's print the next 2000 characters
    print(js_text[idx:idx+3000])
else:
    print("Function not found!")
