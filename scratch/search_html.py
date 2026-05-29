with open("scratch/powerbi_page.html", "r", encoding="utf-8") as f:
    html = f.read()

print("HTML Length:", len(html))

# Check for keywords
for kw in ["2024", "2025", "2026", "Año", "Periodo", "Campaña", "Chicharrita", "Dalbulus", "Maiz"]:
    print(f"Keyword '{kw}': Count: {html.lower().count(kw.lower())}")

# Let's print out all divs/elements containing "2024"
import re
print("\nElements with 2024:")
matches = re.findall(r'(<[^>]*>[^<]*2024[^<]*</[^>]*>)', html)
for m in matches[:10]:
    print("-", repr(m))
