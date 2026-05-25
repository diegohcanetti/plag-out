import pandas as pd
from loaders.db import get_engine

def main():
    engine = get_engine()
    # Check count of climate telemetry table
    try:
        count_df = pd.read_sql_query("SELECT COUNT(*) as cnt FROM climate_telemetry", con=engine)
        print(f"Total rows in climate_telemetry: {count_df['cnt'].iloc[0]}")
        
        # Check first 5 rows to see structure
        sample_df = pd.read_sql_query("SELECT * FROM climate_telemetry LIMIT 5", con=engine)
        print("\nSample records:")
        print(sample_df)
    except Exception as e:
        print(f"Error querying climate_telemetry: {e}")

if __name__ == "__main__":
    main()
