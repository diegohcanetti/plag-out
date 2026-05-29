import json

with open("scratch/querydata_4.json", "r", encoding="utf-8") as f:
    data = json.load(f)

result_data = data["results"][0]["result"]["data"]
dm0 = result_data["dsr"]["DS"][0]["PH"][0]["DM0"]
value_dicts = result_data["dsr"]["DS"][0]["ValueDicts"]

# Dictionaries
d0 = value_dicts.get("D0", [])
d1 = value_dicts.get("D1", [])
d2 = value_dicts.get("D2", [])

print("D0 length:", len(d0))
print("D1 length:", len(d1))
print("D2 length:", len(d2))

rows = []
current_row = [None, None, None, None]

for idx, item in enumerate(dm0):
    # If the item defines 'S', it's a schema/header item, but it can also contain 'C'
    c_vals = item.get("C", [])
    
    # Update current_row with c_vals
    for i, val in enumerate(c_vals):
        current_row[i] = val
        
    # How many times to repeat or output?
    # In PowerBI, if 'R' is present, it's a bitmask or repeat count.
    # Actually, let's print some items and see how the rows are formed.
    # Let's print the state of current_row
    row_copy = list(current_row)
    
    # Map indices to actual values
    val_0 = row_copy[0] # Index
    val_1 = d0[row_copy[1]] if row_copy[1] is not None and row_copy[1] < len(d0) else None
    val_2 = d1[row_copy[2]] if row_copy[2] is not None and row_copy[2] < len(d1) else None
    val_3 = d2[row_copy[3]] if row_copy[3] is not None and row_copy[3] < len(d2) else None
    
    print(f"Record {idx}: C={c_vals}, R={item.get('R')}, Decoded=({val_0}, {val_1}, {val_2}, {val_3})")
    
    if idx >= 40:
        break
