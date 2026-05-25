import pandas as pd
from loaders.db import get_engine

def main():
    engine = get_engine()
    query = (
        "SELECT id, occurrence_date, pest_type, severity_level, institution, "
        "province, locality, adults_count, infection_percent, ST_AsText(geom) as geom_wkt "
        "FROM pest_monitoring"
    )
    df = pd.read_sql_query(query, con=engine)
    
    total_rows = len(df)
    print(f"Total rows in pest_monitoring: {total_rows}")
    
    # Check for completely identical rows (excluding 'id' because id is unique/autoincrement)
    fields_to_check = [c for c in df.columns if c != 'id']
    exact_duplicates = df.duplicated(subset=fields_to_check, keep=False).sum()
    print(f"Number of exact duplicates (excluding ID): {exact_duplicates} ({exact_duplicates / total_rows * 100:.2f}%)")
    
    # Check for duplicates by core logical key: occurrence_date, pest_type, locality, province, geom_wkt
    key_fields = ['occurrence_date', 'pest_type', 'locality', 'province', 'geom_wkt']
    key_duplicates = df.duplicated(subset=key_fields, keep=False).sum()
    print(f"Number of duplicate records on core keys (same date, species, location): {key_duplicates} ({key_duplicates / total_rows * 100:.2f}%)")

    # Let's count unique locations
    unique_locations = df['geom_wkt'].nunique()
    print(f"Unique location coordinates: {unique_locations}")
    
    # Let's print some duplicate examples if they exist
    if exact_duplicates > 0:
        print("\n--- Example exact duplicates ---")
        print(df[df.duplicated(subset=fields_to_check, keep=False)].sort_values(by=fields_to_check).head(10).to_string())

if __name__ == "__main__":
    main()
