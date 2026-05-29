import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    q3 = json.load(f)

dm3 = q3["results"][0]["result"]["data"]["dsr"]["DS"][0]["PH"][0]["DM0"]
print("DM3 length:", len(dm3))

# Print the first item in full detail
print("\nFirst item:")
print(json.dumps(dm3[0], indent=2))

# Print the second item in full detail
if len(dm3) > 1:
    print("\nSecond item:")
    print(json.dumps(dm3[1], indent=2))
