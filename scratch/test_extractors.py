import logging
import asyncio
from extractors.aapresid import extract_aapresid_data
from extractors.powerbi_maiz import extract_powerbi_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def test_extractors():
    print("\n--- TESTING AAPRESID EXTRACTOR ---")
    try:
        # Only query 2023/2024 to keep it fast
        aap_recs = extract_aapresid_data(seasons=["2023/2024"])
        print(f"Extracted {len(aap_recs)} records from AAPRESID map.")
        if aap_recs:
            print("First 3 records:")
            for r in aap_recs[:3]:
                print(f"  Pest={r.pest_type} Date={r.occurrence_date.date()} Locality={r.locality} Prov={r.province} Severity={r.severity_level} Infection={r.infection_percent}%")
    except Exception as e:
        print(f"AAPRESID Extractor failed: {e}")
        
    print("\n--- TESTING POWERBI EXTRACTOR ---")
    try:
        pbi_recs = extract_powerbi_data()
        print(f"Extracted {len(pbi_recs)} records from PowerBI dashboard.")
        if pbi_recs:
            print("First 3 records:")
            for r in pbi_recs[:3]:
                print(f"  Pest={r.pest_type} Date={r.occurrence_date.date()} Locality={r.locality} Prov={r.province} Lat={r.latitude:.4f} Lon={r.longitude:.4f} Severity={r.severity_level}")
    except Exception as e:
        print(f"PowerBI Extractor failed: {e}")

if __name__ == "__main__":
    test_extractors()
