import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    q3 = json.load(f)

result_data = q3["results"][0]["result"]["data"]
dm1 = result_data["dsr"]["DS"][0]["PH"][0]["DM0"][0]["M"][0]["DM1"]

print("DM1 Length:", len(dm1))
# Find if there are any elements with 'C' having 3 elements or other keys
for idx, item in enumerate(dm1):
    c = item.get("C", [])
    if len(c) > 2:
        print(f"Item {idx} has {len(c)} elements: {item}")
    # Check if there are other keys besides 'C' and 'R' and 'S'
    other_keys = [k for k in item.keys() if k not in ["C", "R", "S"]]
    if other_keys:
        print(f"Item {idx} has other keys {other_keys}: {item}")
        
print("Let's look at the first item S description:")
if "S" in dm1[0]:
    print(dm1[0]["S"])
