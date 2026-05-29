import json

with open("scratch/querydata_1.json", "r", encoding="utf-8") as f:
    data = json.load(f)

result_data = data["results"][0]["result"]["data"]
dm0 = result_data["dsr"]["DS"][0]["PH"][0]["DM0"]
print("DM0 Length in Q1:", len(dm0))

# Print first 20 records in Q1
for idx, r in enumerate(dm0[:20]):
    print(f"  {idx}: {r}")
