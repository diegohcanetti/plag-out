import json

with open("scratch/querydata_4.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Find all dictionary keys recursively
def search_dict(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else k
            if k in ["ValueDicts", "valueDicts", "values", "V", "D"]:
                print(f"Found key '{k}' at path '{current_path}': Type: {type(v)}")
                if isinstance(v, dict):
                    print("  Keys:", list(v.keys()))
                elif isinstance(v, list):
                    print(f"  Length: {len(v)}, first 5: {v[:5]}")
            search_dict(v, current_path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            search_dict(item, f"{path}[{idx}]")

search_dict(data)
