import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    q3 = json.load(f)

result_data = q3["results"][0]["result"]["data"]
dm0 = result_data["dsr"]["DS"][0]["PH"][0]["DM0"]

print("DM3 length:", len(dm0))

# Print first item's structure and keys
first_item = dm0[0]
print("First item keys:", list(first_item.keys()))
if "G0" in first_item:
    print("G0 value:", first_item["G0"])
if "M" in first_item:
    m_list = first_item["M"]
    print("M list length:", len(m_list))
    if m_list:
        first_m = m_list[0]
        print("  first_m keys:", list(first_m.keys()))
        if "DM1" in first_m:
            dm1_list = first_m["DM1"]
            print("    DM1 list length:", len(dm1_list))
            print("    First 10 items in DM1:")
            for idx, item in enumerate(dm1_list[:10]):
                print(f"      {idx}: {item}")
