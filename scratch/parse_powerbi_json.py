import json

def inspect_file(path):
    print(f"\n================ INSPECTING {path} ================")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    results = data.get("results", [])
    if not results:
        print("No results found!")
        return
        
    result_data = results[0].get("result", {}).get("data", {})
    descriptor = result_data.get("descriptor", {})
    select_fields = descriptor.get("Select", [])
    print("Select Fields:")
    for fld in select_fields:
        print(f"  {fld}")
        
    ds_result = result_data.get("dsQueryResult", {})
    print("dsQueryResult Keys:", list(ds_result.keys()))
    
    # Check if there is data shapes or dm
    shapes = ds_result.get("O", [])
    if shapes:
        print("Number of O (records/shapes):", len(shapes))
        # Print a snippet of first O record
        first_o = str(shapes[0])[:500]
        print(f"First O record: {first_o}...")
        
    # Let's inspect data shapes directly
    for key in ds_result.keys():
        val = ds_result[key]
        if isinstance(val, list) and val:
            print(f"Key '{key}' length: {len(val)}, first element type: {type(val[0])}")
            if isinstance(val[0], dict):
                print(f"  First element keys: {list(val[0].keys())}")
                
inspect_file("scratch/querydata_3.json")
inspect_file("scratch/querydata_4.json")
