"""
Dataset Extraction Script

This script extracts data from the local PostgreSQL database (pest_monitoring 
and climate_telemetry tables) and exports them into CSV and Parquet formats.
These datasets can be handed off to the Machine Learning team for fallback exploration
(Secondary Pests and Biocontrol).
"""

import os
import logging
import pandas as pd
from sqlalchemy import text
from loaders.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("export_datasets")

def export_table_to_csv(table_name: str, output_dir: str):
    engine = get_engine()
    
    # We use PostGIS ST_AsText to extract the geography columns into WKT format
    # so they can be parsed as text by pandas.
    if table_name == "pest_monitoring":
        query = "SELECT id, occurrence_date, pest_type, severity_level, institution, province, locality, adults_count, infection_percent, ST_AsText(geom) as geom_wkt FROM pest_monitoring"
    elif table_name == "climate_telemetry":
        query = "SELECT time, location_id, temp_max, humidity, precipitation, ST_AsText(location) as location_wkt FROM climate_telemetry"
    else:
        query = f"SELECT * FROM {table_name}"
        
    logger.info(f"Extracting {table_name} from database...")
    
    try:
        # Read SQL query directly into a pandas DataFrame
        df = pd.read_sql_query(query, engine)
        
        if df.empty:
            logger.warning(f"No data found in {table_name} table.")
            return
            
        logger.info(f"Extracted {len(df)} rows from {table_name}.")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Export to CSV
        csv_path = os.path.join(output_dir, f"{table_name}_dataset.csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"Successfully exported {table_name} to {csv_path}")
        
    except Exception as e:
        logger.error(f"Failed to export {table_name}: {e}")

def main():
    output_dir = "data/exports"
    logger.info(f"Starting dataset extraction to '{output_dir}' directory.")
    
    export_table_to_csv("pest_monitoring", output_dir)
    export_table_to_csv("climate_telemetry", output_dir)
    
    logger.info("Dataset extraction complete.")

if __name__ == "__main__":
    main()
