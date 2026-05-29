import json

for i in range(5):
    path = f"scratch/querydata_{i}.json"
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    print(f"File {path}:")
    for yr in ["2024", "2025", "2026"]:
        print(f"  Count for '{yr}': {text.count(yr)}")
