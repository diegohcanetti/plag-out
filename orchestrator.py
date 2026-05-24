"""
Plag-out Data Pipeline Master Orchestrator

This is the main entry point for the Plag-out ETL data pipeline. It orchestrates
the extraction of agricultural data (MAIZAR, SINAVIMO, GBIF), spatial normalization,
weather fetching via NASA POWER, and final database loading into the local PostGIS/TimescaleDB tables.

Usage:
    PYTHONPATH=. python orchestrator.py --test
    PYTHONPATH=. python orchestrator.py --limit-reports 5
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


def run_pipeline(
    limit_records: Optional[int] = None, 
    limit_reports: Optional[int] = None, 
    test_mode: bool = False
) -> None:
    """
    Orchestrates the entire ETL pipeline, processing historical reports to build a massive dataset.
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
        all_maizar_records = []
    else:
        # Determine how many reports to process
        if test_mode and limit_reports is None:
            limit_reports = 2
            
        if limit_reports:
            logger.info(f"Limiting to the first {limit_reports} discovered reports.")
            reports_to_process = maizar_pages[:limit_reports]
        else:
            reports_to_process = maizar_pages
            
        logger.info(f"Discovered {len(maizar_pages)} reports. Will process {len(reports_to_process)} reports.")
        
        all_maizar_records = []
        for i, report in enumerate(reports_to_process):
            logger.info(f"--- Processing Report {i+1}/{len(reports_to_process)}: {report['title']} (Number: {report['report_num']}) ---")
            
            # Determine date
            if report.get("date"):
                try:
                    report_date = datetime.strptime(report["date"], "%d/%m/%Y")
                    logger.info(f"Parsed report date: {report_date.strftime('%Y-%m-%d')}")
                except Exception as e:
                    logger.warning(f"Failed to parse report date '{report['date']}': {e}. Using current time.")
                    report_date = datetime.now()
            else:
                logger.warning(f"No date listed for report {report['title']}. Using current time.")
                report_date = datetime.now()
                
            # Download PDF
            pdf_url = fetch_pdf_url_from_page(report["url"])
            if not pdf_url:
                logger.error(f"Failed to resolve PDF url for: {report['title']}. Skipping.")
                continue
                
            pdf_path = f"data/maizar_pdfs/report_{report['report_num'] or report['id']}.pdf"
            os.makedirs("data/maizar_pdfs", exist_ok=True)
            
            logger.info("Downloading PDF...")
            download_pdf(pdf_url, pdf_path)
            
            # Parse the PDF
            logger.info("Parsing PDF text and converting to structured data...")
            try:
                maizar_records = parse_maizar_pdf(pdf_path, report_date)
            except Exception as e:
                logger.error(f"Failed to parse PDF {pdf_path}: {e}. Skipping report.")
                continue
                
            # Trim the records BEFORE geocoding to prevent excessive API queries in test/limit mode
            if test_mode and maizar_records:
                logger.info(f"Test mode: trimming MAIZAR records from {len(maizar_records)} to 3.")
                maizar_records = maizar_records[:3]
            elif limit_records and maizar_records:
                logger.info(f"Limiting MAIZAR records from {len(maizar_records)} to {limit_records}.")
                maizar_records = maizar_records[:limit_records]
                
            # Geo-reference the locations using cached SpatialGeocoder
            logger.info(f"Applying spatial geocoding to {len(maizar_records)} records...")
            for idx, rec in enumerate(maizar_records):
                lat, lon = geocoder.geocode(rec.locality, rec.province)
                rec.latitude = lat
                rec.longitude = lon
                
            # Ingest MAIZAR biological data for this report immediately
            if maizar_records:
                logger.info(f"Ingesting {len(maizar_records)} normalized records into postgres...")
                try:
                    ingest_pest_records(maizar_records)
                    all_maizar_records.extend(maizar_records)
                except Exception as e:
                    logger.error(f"Failed to ingest MAIZAR pest records: {e}")

    # Step 3: Weather extraction from NASA POWER for each unique MAIZAR coordinate and occurrence date
    if all_maizar_records:
        logger.info("Step 2: Harvesting agrometeorological daily climate telemetry from NASA POWER...")
        # Extract unique combination of (latitude, longitude, date)
        unique_coord_dates = set(
            (rec.latitude, rec.longitude, rec.occurrence_date)
            for rec in all_maizar_records
            if rec.latitude != 0.0
        )
        
        logger.info(f"Found {len(unique_coord_dates)} unique spatial-temporal coordinates to harvest weather.")
        
        climate_records = []
        # Query and batch-ingest to keep memory low and report progress
        for idx, (lat, lon, occ_date) in enumerate(unique_coord_dates):
            end_date_str = occ_date.strftime("%Y-%m-%d")
            start_date_str = (occ_date - timedelta(days=9)).strftime("%Y-%m-%d")
            
            logger.info(f"[{idx+1}/{len(unique_coord_dates)}] Fetching climate for ({lat:.4f}, {lon:.4f}) around {end_date_str}...")
            try:
                weather_recs = extract_nasa_climate(lat, lon, start_date_str, end_date_str)
                climate_records.extend(weather_recs)
            except Exception as e:
                logger.error(f"Failed to fetch climate variables for ({lat}, {lon}) at {end_date_str}: {e}")
                
            # Ingest in chunks of 50 locations (approx 500 records) to keep database transactions healthy
            if len(climate_records) >= 500:
                logger.info(f"Ingesting {len(climate_records)} weather metrics into climate_telemetry hypertable...")
                try:
                    ingest_climate_telemetry(climate_records)
                    climate_records = []
                except Exception as e:
                    logger.error(f"Failed to ingest climate variables batch: {e}")
                    
        # Ingest remaining climate records
        if climate_records:
            logger.info(f"Ingesting remaining {len(climate_records)} weather metrics into climate_telemetry...")
            try:
                ingest_climate_telemetry(climate_records)
            except Exception as e:
                logger.error(f"Failed to ingest remaining climate variables: {e}")

    # Step 4: INGEST Extra Integrations (SINAVIMO Ground Truth and GBIF climatic niches)
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
    parser.add_argument("--limit-reports", type=int, help="Limit number of MAIZAR reports to process")
    args = parser.parse_args()

    run_pipeline(
        limit_records=args.limit, 
        limit_reports=args.limit_reports, 
        test_mode=args.test
    )
