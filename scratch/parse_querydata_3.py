import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    data = json.load(f)

result_data = data["results"][0]["result"]["data"]
dm0 = result_data["dsr"]["DS"][0]["PH"][0]["DM0"]

print("Length of DM0 in querydata_3:", len(dm0))
for idx, item in enumerate(dm0[:30]):
    print(f"Item {idx}: {item}")
