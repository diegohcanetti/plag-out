import requests

url = "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/js/mapasMalezas/jsMapa.js?v2024-11-v02"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
res = requests.get(url, headers=headers)
print("JS File Length:", len(res.text))

# Let's search for getResultMapa in the JS file content
import re
print("Occurrences of getResultMapa:")
for match in re.finditer(r'getResultMapa', res.text):
    start = max(0, match.start() - 100)
    end = min(len(res.text), match.end() + 100)
    print("Context:", repr(res.text[start:end]))
    print("-" * 40)
