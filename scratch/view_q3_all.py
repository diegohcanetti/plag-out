import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    q3 = json.load(f)

# Let's search for lists of strings in the entire JSON
def search_lists(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            search_lists(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], str):
            print(f"Found string list at '{path}' of length {len(obj)}:")
            print(f"  First 10: {obj[:10]}")
        else:
            for idx, item in enumerate(obj):
                search_lists(item, f"{path}[{idx}]")

search_lists(q3)
