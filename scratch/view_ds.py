import json

with open("scratch/querydata_4.json", "r", encoding="utf-8") as f:
    data = json.load(f)

result_data = data["results"][0]["result"]["data"]
dm0 = result_data["dsr"]["DS"][0]["PH"][0]["DM0"]
print("DM0 Type in querydata_4.json:", type(dm0))
if isinstance(dm0, list):
    print("DM0 Length:", len(dm0))
    # Print first 20 items
    for item in dm0[:20]:
        print("-", item)
