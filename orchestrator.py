"""
Plag-out Data Pipeline Master Orchestrator

This is the main entry point for the Plag-out ETL data pipeline. It orchestrates
the extraction of agricultural data (MAIZAR, SINAVIMO, GBIF), spatial normalization,
weather fetching via NASA POWER, and final database loading into the local PostGIS/TimescaleDB tables.

Usage:
    PYTHONPATH=. python orchestrator.py --test
"""

import os
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Optional

# Import loaders
from loaders.db import execute_migration_queries, get_engine
from loaders.ingest import ingest_pest_records, ingest_climate_telemetry

# Import extractors and transformers
from extractors.maizar import fetch_report_pages, download_pdf, fetch_pdf_url_from_page
from transformers.maizar_pdf import parse_maizar_pdf
from transformers.spatial import SpatialGeocoder
from extractors.nasa_power import extract_nasa_climate
from extractors.gbif import extract_gbif_occurrences
from extractors.sinavimo import extract_sinavimo_alerts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("orchestrator")


def run_pipeline(limit_records: Optional[int] = None, test_mode: bool = False) -> None:
    """
    Orchestrates the entire ETL pipeline.
    """
    logger.info("Initializing database migrations and tables check...")
    try:
        execute_migration_queries()
    except Exception as e:
        logger.warning(f"Migration queries threw warning (could be already completed columns): {e}")

    # Step 1: Initialize spatial geocoder
    geocoder = SpatialGeocoder()

    # Step 2: MAIZAR Pest Records Extraction & Transformation
    logger.info("Step 1: Scraping MAIZAR portal for Dalbulus maidis reports...")
    maizar_pages = fetch_report_pages()
    
    if not maizar_pages:
        logger.error("No MAIZAR reports discovered. Skipping MAIZAR step.")
        maizar_records: List = []
    else:
        # Use the latest report for our pipeline run
        latest_report = maizar_pages[0]
        logger.info(f"Discovered latest report: {latest_report['title']} (Number: {latest_report['report_num']})")
        
        # Determine date. Default to today if we cannot parse it easily, or base it on report date if available
        # In a production run, we can crawl the publication date from the page.
        report_date = datetime.now()
        
        # Download PDF
        pdf_url = fetch_pdf_url_from_page(latest_report["url"])
        if not pdf_url:
            logger.error(f"Failed to resolve PDF url for: {latest_report['title']}")
            maizar_records = []
        else:
            pdf_path = f"data/maizar_pdfs/report_{latest_report['report_num'] or latest_report['id']}.pdf"
            os.makedirs("data/maizar_pdfs", exist_ok=True)
            
            logger.info("Downloading PDF...")
            download_pdf(pdf_url, pdf_path)
            
            # Parse the PDF
            logger.info("Parsing PDF text and converting to structured data...")
            maizar_records = parse_maizar_pdf(pdf_path, report_date)
            
            # In test/limit mode, we trim the records BEFORE geocoding to prevent excessive API queries
            if test_mode and maizar_records:
                logger.info(f"Test mode: trimming MAIZAR records from {len(maizar_records)} to 3.")
                maizar_records = maizar_records[:3]
            elif limit_records and maizar_records:
                logger.info(f"Limiting MAIZAR records from {len(maizar_records)} to {limit_records}.")
                maizar_records = maizar_records[:limit_records]
            
            # Geo-reference the locations using Nominatim fallback
            logger.info("Applying spatial geocoding to MAIZAR records...")
            for idx, rec in enumerate(maizar_records):
                # Geocode locality + province
                lat, lon = geocoder.geocode(rec.locality, rec.province)
                rec.latitude = lat
                rec.longitude = lon

    # Step 3: Ingest MAIZAR biological data
    if maizar_records:
        logger.info(f"Ingesting {len(maizar_records)} normalized MAIZAR records into local postgres...")
        try:
            ingest_pest_records(maizar_records)
        except Exception as e:
            logger.error(f"Failed to ingest MAIZAR pest records: {e}")

    # Step 4: Weather extraction from NASA POWER for each unique MAIZAR coordinate
    logger.info("Step 2: Harvesting agrometeorological daily climate telemetry from NASA POWER...")
    unique_coords = set((rec.latitude, rec.longitude) for rec in maizar_records if rec.latitude != 0.0)
    
    climate_records = []
    for lat, lon in unique_coords:
        # Define historical temporal query window (e.g. 10 days trailing the occurrence)
        end_date_str = (report_date).strftime("%Y-%m-%d")
        start_date_str = (report_date - timedelta(days=9)).strftime("%Y-%m-%d")
        
        try:
            weather_recs = extract_nasa_climate(lat, lon, start_date_str, end_date_str)
            climate_records.extend(weather_recs)
        except Exception as e:
            logger.error(f"Failed to fetch climate variables for coordinates ({lat}, {lon}): {e}")

    # Ingest climate variables into TimescaleDB hypertable
    if climate_records:
        logger.info(f"Ingesting {len(climate_records)} weather metrics into climate_telemetry hypertable...")
        try:
            ingest_climate_telemetry(climate_records)
        except Exception as e:
            logger.error(f"Failed to ingest climate variables: {e}")

    # Step 5: INGEST Extra Integrations (SINAVIMO Ground Truth and GBIF climatic niches)
    logger.info("Step 3: Ingesting GBIF and SINAVIMO occurrences for niches validation...")
    try:
        gbif_limit = 5 if test_mode else 100
        gbif_records = extract_gbif_occurrences("Spodoptera frugiperda", limit=gbif_limit)
        ingest_pest_records(gbif_records)
    except Exception as e:
        logger.error(f"Failed to fetch/load GBIF occurrences: {e}")

    try:
        sinavimo_records = extract_sinavimo_alerts()
        ingest_pest_records(sinavimo_records)
    except Exception as e:
        logger.error(f"Failed to fetch/load SINAVIMO official alerts: {e}")

    logger.info("End-to-End Plag-out Pipeline Execution complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plag-out ETL Orchestrator")
    parser.add_argument("--test", action="store_true", help="Runs pipeline in test mode with small sample sizes")
    parser.add_argument("--limit", type=int, help="Limit number of parsed MAIZAR locations")
    args = parser.parse_args()

    run_pipeline(limit_records=args.limit, test_mode=args.test)
