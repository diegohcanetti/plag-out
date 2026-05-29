import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    data = json.load(f)

result_data = data["results"][0]["result"]["data"]
print("result_data Keys:", list(result_data.keys()))

# Let's inspect each key
for k, v in result_data.items():
    print(f"Key '{k}': Type: {type(v)}")
    if isinstance(v, dict):
        print(f"  Keys: {list(v.keys())}")
        # If there are subkeys, let's print them
        for sk, sv in v.items():
            print(f"    Subkey '{sk}': Type: {type(sv)}")
            if isinstance(sv, dict):
                print(f"      Subkeys: {list(sv.keys())}")
            elif isinstance(sv, list):
                print(f"      Length: {len(sv)}")

# Let's inspect dsQueryResult key structure in result_data
if "dsQueryResult" in result_data:
    ds = result_data["dsQueryResult"]
    print("\ndsQueryResult type:", type(ds))
    if isinstance(ds, dict):
        print("dsQueryResult keys:", list(ds.keys()))
        for k, v in ds.items():
            print(f"  Key '{k}': Type: {type(v)}")
            if isinstance(v, list):
                print(f"    Length: {len(v)}")
                if v:
                    print(f"    First item type: {type(v[0])}")
                    if isinstance(v[0], dict):
                        print(f"    First item keys: {list(v[0].keys())}")
