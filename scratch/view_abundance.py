import json

with open("scratch/sample_abundance_response.json", "r", encoding="utf-8") as f:
    data = json.load(f)

meds = data.get("aMalezaDeptoMediciones", {})
for year, content in meds.items():
    print(f"Year: {year}")
    for pest, records in content.items():
        print(f"  Pest: {pest}, Type: {type(records)}")
        if isinstance(records, dict):
            print(f"    Number of keys: {len(records)}")
            first_keys = list(records.keys())[:5]
            print(f"    First few keys: {first_keys}")
            for k in first_keys:
                print(f"      Key '{k}': {records[k]}")
        elif isinstance(records, list):
            print(f"    Length of list: {len(records)}")
            if records:
                print(f"    First record: {records[0]}")
