import json

with open("scratch/querydata_4.json", "r", encoding="utf-8") as f:
    data = json.load(f)

vd = data["results"][0]["result"]["data"]["dsr"]["DS"][0]["ValueDicts"]
d0 = vd.get("D0", [])
print(f"Total units: {len(d0)}")
for i, unit in enumerate(d0):
    print(f"'{unit}',")
