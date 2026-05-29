import json

with open("scratch/querydata_3.json", "r", encoding="utf-8") as f:
    q3 = json.load(f)

result_data = q3["results"][0]["result"]["data"]
dm0 = result_data["dsr"]["DS"][0]["PH"][0]["DM0"]

if len(dm0) > 1:
    item2 = dm0[1]
    print("Second item keys:", list(item2.keys()))
    if "G0" in item2:
        print("G0 value:", item2["G0"])
    if "M" in item2:
        m_list = item2["M"]
        print("M list length:", len(m_list))
        if m_list and "DM1" in m_list[0]:
            print("  DM1 length in item 2:", len(m_list[0]["DM1"]))
            print("  First 5 in DM1 item 2:")
            for idx, r in enumerate(m_list[0]["DM1"][:5]):
                print(f"    {idx}: {r}")
