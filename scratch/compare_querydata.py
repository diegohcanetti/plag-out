import json

# Let's inspect querydata_3.json in more detail
with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    q3 = json.load(f)

result_3 = q3["results"][0]["result"]["data"]
dm3 = result_3["dsr"]["DS"][0]["PH"][0]["DM0"]
value_dicts_3 = result_3["dsr"]["DS"][0].get("ValueDicts", {})

print("ValueDicts in Q3:", list(value_dicts_3.keys()))
for k, v in value_dicts_3.items():
    print(f"  Key {k}: len {len(v)}, first 5: {v[:5]}")

print("First 15 DM0 in Q3:")
for idx, r in enumerate(dm3[:15]):
    print(f"  {idx}: {r}")

# Let's see if we have similar keys in querydata_4.json
with open("scratch/querydata_4.json", "r", encoding="utf-8") as f:
    q4 = json.load(f)
result_4 = q4["results"][0]["result"]["data"]
value_dicts_4 = result_4["dsr"]["DS"][0].get("ValueDicts", {})
print("\nValueDicts in Q4:", list(value_dicts_4.keys()))
for k, v in value_dicts_4.items():
    print(f"  Key {k}: len {len(v)}, first 5: {v[:5]}")
