import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    q3 = json.load(f)

dm3 = q3["results"][0]["result"]["data"]["dsr"]["DS"][0]["PH"][0]["DM0"]
print("DM3 length:", len(dm3))
for idx, r in enumerate(dm3[:20]):
    print(f"Index {idx}: {r}")
