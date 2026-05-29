import json

with open("scratch/querydata_4.json", "r", encoding="utf-8") as f:
    data = json.load(f)

vd = data["results"][0]["result"]["data"]["dsr"]["DS"][0]["ValueDicts"]
d2 = vd.get("D2", [])
print(f"Total periods: {len(d2)}")
for p in d2:
    print("-", p)
