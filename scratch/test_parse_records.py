import json
import re
from datetime import datetime
from transformers.spatial import SpatialGeocoder

def clean_salida(salida_str):
    """
    Parses 'Hembras: X,XX; Machos: Y,YY' to return total count or info.
    """
    if not salida_str:
        return None, None
    try:
        # e.g., 'Hembras: 0,09; Machos: 0,04 (Indvs./golpe de red)'
        # Let's extract numbers
        match = re.search(r'Hembras:\s*([\d,]+);\s*Machos:\s*([\d,]+)', salida_str)
        if match:
            h_str = match.group(1).replace(",", ".")
            m_str = match.group(2).replace(",", ".")
            h = float(h_str)
            m = float(m_str)
            total = h + m
            return total, f"Hembras: {h}; Machos: {m}"
    except Exception:
        pass
    return None, salida_str

def parse_period(period_str):
    """
    Parses '2024 - JUN 3 – JUN 9' to get the starting date of the week.
    """
    # Let's match month and day
    # e.g. '2024 - JUN 3 – JUN 9' -> year=2024, month=June, day=3
    months_es_en = {
        'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
    }
    try:
        match = re.search(r'(\d{4})\s*-\s*([A-Z]{3})\s*(\d+)', period_str)
        if match:
            year = int(match.group(1))
            month_str = match.group(2)
            day = int(match.group(3))
            month = months_es_en.get(month_str, 6)
            return datetime(year, month, day)
    except Exception:
        pass
    return datetime.now()

def main():
    geocoder = SpatialGeocoder()
    
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

    current_row = [None, None, None, None]
    decoded_records = []

    for idx, item in enumerate(dm0):
        c_vals = item.get("C", [])
        for i, val in enumerate(c_vals):
            current_row[i] = val
            
        row_copy = list(current_row)
        
        # Resolve values
        idx_val = row_copy[0]
        unit_name = d0[row_copy[1]] if row_copy[1] is not None and row_copy[1] < len(d0) else None
        salida_val = d1[row_copy[2]] if row_copy[2] is not None and row_copy[2] < len(d1) else None
        period_val = d2[row_copy[3]] if row_copy[3] is not None and row_copy[3] < len(d2) else None
        
        if not unit_name or not period_val:
            continue
            
        occ_date = parse_period(period_val)
        total_count, clean_sal = clean_salida(salida_val)
        
        # Geocode the INTA Unit name
        # To get best results, prefix "INTA " if not present
        search_name = unit_name if "inta" in unit_name.lower() else f"INTA {unit_name}"
        lat, lon = geocoder.geocode(search_name, "Argentina")
        
        # Determine severity level
        if total_count is not None:
            if total_count == 0.0:
                sev = "Absent"
            elif total_count <= 0.1:
                sev = f"Low ({total_count:.2f} Indvs/golpe)"
            elif total_count <= 0.5:
                sev = f"Medium ({total_count:.2f} Indvs/golpe)"
            else:
                sev = f"High ({total_count:.2f} Indvs/golpe)"
        else:
            sev = "Present"
            
        decoded_records.append({
            "date": occ_date.strftime("%Y-%m-%d"),
            "unit": unit_name,
            "salida": salida_val,
            "period": period_val,
            "coords": (lat, lon),
            "severity": sev,
            "count": total_count
        })

    print(f"\nSuccessfully parsed {len(decoded_records)} records!")
    print("Sample parsed records:")
    for r in decoded_records[:10]:
        print(f"Date={r['date']} Unit={r['unit']} Coords={r['coords']} Severity={r['severity']} RawSalida={r['salida']}")

if __name__ == "__main__":
    main()
