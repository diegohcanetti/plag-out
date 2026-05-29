import json
import os

for idx in range(5):
    path = f"scratch/querydata_{idx}.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        results = data.get("results", [])
        if results:
            res_data = results[0].get("result", {}).get("data", {})
            descriptor = res_data.get("descriptor", {})
            select = descriptor.get("Select", [])
            print(f"\nFile querydata_{idx}.json (size {os.path.getsize(path)} bytes):")
            print("Select Fields:")
            for s in select:
                print("  ", s.get("Name"))
            
            # Check ValueDicts keys
            dsr = res_data.get("dsr", {})
            ds_list = dsr.get("DS", [])
            if ds_list:
                vd = ds_list[0].get("ValueDicts", {})
                print("ValueDicts Keys:", list(vd.keys()))
                for k, v in vd.items():
                    print(f"  {k}: length {len(v)}, first 3: {v[:3]}")
