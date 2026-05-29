import requests

url = "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/"
payload = {
    "tipo_mapa": "presencia_maleza",
    "filtros_malezas[]": "maiz-temprano",
    "malezas[]": "chicharrita-en-maiz-temprano",
    "anosPM[]": "2023/2024"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}

print("Sending POST request to AAPRESID...")
res = requests.post(url, data=payload, headers=headers)
print("Status:", res.status_code)
print("Length of response:", len(res.text))

# Let's search the HTML response for any javascript variable definitions like aDepartamentos or arrays of data
import re
matches = re.findall(r'var\s+\w+\s*=\s*[^;]+;', res.text)
print("\nFound javascript variables in response:")
for m in matches[:20]:
    print("-", m)

# Let's write the response HTML to a file so we can view it
with open("scratch/post_response.html", "w", encoding="utf-8") as f:
    f.write(res.text)
print("Saved response to scratch/post_response.html")
