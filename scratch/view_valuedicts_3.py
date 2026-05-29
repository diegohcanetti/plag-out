import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    data = json.load(f)

vd = data["results"][0]["result"]["data"]["dsr"]["DS"][0]["ValueDicts"]
for k, v in vd.items():
    print(f"ValueDict Key '{k}': Length: {len(v)}")
    print(f"  First 10 values: {v[:10]}")
