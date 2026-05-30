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
import concurrent.futures
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd


# Import loaders
from loaders.db import execute_migration_queries, get_engine, get_etl_watermark, update_etl_watermark
from loaders.ingest import ingest_pest_records, ingest_climate_telemetry

# Import extractors and transformers
from extractors.maizar import fetch_report_pages, download_pdf, fetch_pdf_url_from_page
from transformers.maizar_pdf import parse_maizar_pdf
from transformers.spatial import SpatialGeocoder
from extractors.nasa_power import extract_nasa_climate
from extractors.openmeteo import extract_openmeteo_climate
from extractors.gbif import extract_gbif_occurrences
from extractors.sinavimo import extract_sinavimo_alerts
from extractors.aapresid import extract_aapresid_data
from extractors.aappce import extract_aappce_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("orchestrator")


def validate_pest_records_dataframe(df: pd.DataFrame) -> None:
    """
    Validates a DataFrame of pest records using Pandas assertions.
    Ensures:
    1. Critical columns (latitude, longitude, occurrence_date) have 0% null values.
    2. Coordinate bounds fall within South America:
       - Latitude between -60.0 and 15.0
       - Longitude between -90.0 and -30.0
    """
    if df.empty:
        return

    for col in ['latitude', 'longitude', 'occurrence_date']:
        assert col in df.columns, f"Critical column '{col}' is missing from DataFrame."
        null_count = df[col].isnull().sum()
        assert null_count == 0, f"Data Quality Failure: Column '{col}' has {null_count} null value(s)."

    # South America bounds check
    lat_min, lat_max = -60.0, 15.0
    lon_min, lon_max = -90.0, -30.0

    out_of_bounds_lat = df[(df['latitude'] < lat_min) | (df['latitude'] > lat_max)]
    assert out_of_bounds_lat.empty, (
        f"Data Quality Failure: Latitude values out of South America bounds [{lat_min}, {lat_max}]: "
        f"{out_of_bounds_lat['latitude'].tolist()}"
    )

    out_of_bounds_lon = df[(df['longitude'] < lon_min) | (df['longitude'] > lon_max)]
    assert out_of_bounds_lon.empty, (
        f"Data Quality Failure: Longitude values out of South America bounds [{lon_min}, {lon_max}]: "
        f"{out_of_bounds_lon['longitude'].tolist()}"
    )


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
    maizar_watermark = get_etl_watermark("MAIZAR")
    logger.info(f"MAIZAR ETL watermark: {maizar_watermark}")
    
    maizar_pages = fetch_report_pages()
    
    if not maizar_pages:
        logger.error("No MAIZAR reports discovered. Skipping MAIZAR step.")
        all_maizar_records = []
    else:
        # Filter reports by watermark date if available
        if maizar_watermark:
            filtered_pages = []
            for r in maizar_pages:
                if r.get("date"):
                    try:
                        r_date = datetime.strptime(r["date"], "%d/%m/%Y")
                        if r_date.replace(tzinfo=None) > maizar_watermark.replace(tzinfo=None):
                            filtered_pages.append(r)
                    except:
                        filtered_pages.append(r)
                else:
                    filtered_pages.append(r)
            maizar_pages = filtered_pages

        # Sort chronologically (oldest first) so backfilling with limits works perfectly
        def get_date(r):
            if r.get("date"):
                try:
                    return datetime.strptime(r["date"], "%d/%m/%Y")
                except:
                    pass
            return datetime.min

        maizar_pages.sort(key=get_date)

        # Determine how many reports to process
        if test_mode and limit_reports is None:
            limit_reports = 2
            
        if limit_reports:
            logger.info(f"Limiting to the first {limit_reports} discovered reports.")
            reports_to_process = maizar_pages[:limit_reports]
        else:
            reports_to_process = maizar_pages
            
        logger.info(f"Discovered {len(maizar_pages)} reports to process after filtering by watermark.")
        
        all_maizar_records = []
        latest_report_date = None
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

                # Run ETL Data Quality assertions
                if maizar_records:
                    df_maizar = pd.DataFrame([r.dict() for r in maizar_records])
                    validate_pest_records_dataframe(df_maizar)
                    
                    # Ingest MAIZAR biological data for this report immediately
                    logger.info(f"Ingesting {len(maizar_records)} normalized records into postgres...")
                    ingest_pest_records(maizar_records)
                    all_maizar_records.extend(maizar_records)
                    if report_date and (latest_report_date is None or report_date > latest_report_date):
                        latest_report_date = report_date
                else:
                    logger.warning(f"No records found in PDF: {pdf_path}")
            except Exception as e:
                logger.error(f"Data Quality validation or ingestion failed for PDF {pdf_path}: {e}")
                from loaders.db import quarantine_failed_file
                quarantine_failed_file(pdf_path, str(e))
                continue

        if latest_report_date:
            update_etl_watermark("MAIZAR", latest_report_date)

    # Step 3: INGEST Extra Integrations (SINAVIMO, GBIF, AAPRESID, PowerBI)
    logger.info("Step 2: Ingesting auxiliary biological datasets (GBIF, SINAVIMO, AAPRESID, PowerBI)...")
    
    # 3A. GBIF occurrences
    gbif_records = []
    try:
        gbif_watermark = get_etl_watermark("GBIF")
        logger.info(f"GBIF ETL watermark: {gbif_watermark}")
        
        import yaml
        yaml_path = "ml/biofix_params.yaml"
        pests = []
        if os.path.exists(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data:
                pests = [info.get("scientific_name") for info in data.values() if info.get("scientific_name")]
        if not pests:
            pests = ["Dalbulus maidis", "Spodoptera frugiperda"]

        gbif_limit = 5 if test_mode else 100
        logger.info(f"Extracting GBIF occurrences for {len(pests)} species (limit: {gbif_limit} per species)...")
        for pest in pests:
            logger.info(f"Fetching GBIF occurrences for '{pest}'...")
            try:
                pest_gbif_recs = extract_gbif_occurrences(pest, limit=gbif_limit)
                if pest_gbif_recs:
                    if gbif_watermark:
                        pest_gbif_recs = [r for r in pest_gbif_recs if r.occurrence_date.replace(tzinfo=None) > gbif_watermark.replace(tzinfo=None)]
                    if pest_gbif_recs:
                        # Quality Gate Check
                        df_gbif = pd.DataFrame([r.dict() for r in pest_gbif_recs])
                        validate_pest_records_dataframe(df_gbif)
                        
                        ingest_pest_records(pest_gbif_recs)
                        gbif_records.extend(pest_gbif_recs)
            except Exception as ex:
                logger.error(f"Failed to fetch/load GBIF occurrences for '{pest}': {ex}")
                from loaders.db import quarantine_failed_file
                quarantine_failed_file(f"GBIF_API_{pest}", str(ex))
                
        if gbif_records:
            latest_gbif_date = max(r.occurrence_date for r in gbif_records)
            update_etl_watermark("GBIF", latest_gbif_date)
    except Exception as e:
        logger.error(f"Failed to process GBIF occurrences step: {e}")

    # 3B. SINAVIMO alerts
    sinavimo_records = []
    try:
        logger.info("Extracting SINAVIMO official alerts...")
        sinavimo_watermark = get_etl_watermark("SINAVIMO")
        logger.info(f"SINAVIMO ETL watermark: {sinavimo_watermark}")
        
        fetched_sinavimo = extract_sinavimo_alerts()
        if fetched_sinavimo:
            if sinavimo_watermark:
                fetched_sinavimo = [r for r in fetched_sinavimo if r.occurrence_date.replace(tzinfo=None) > sinavimo_watermark.replace(tzinfo=None)]
            if fetched_sinavimo:
                # Quality Gate Check
                df_sinavimo = pd.DataFrame([r.dict() for r in fetched_sinavimo])
                validate_pest_records_dataframe(df_sinavimo)
                
                ingest_pest_records(fetched_sinavimo)
                sinavimo_records.extend(fetched_sinavimo)
                latest_sinavimo_date = max(r.occurrence_date for r in fetched_sinavimo)
                update_etl_watermark("SINAVIMO", latest_sinavimo_date)
    except Exception as e:
        logger.error(f"Failed to fetch/load SINAVIMO official alerts: {e}")
        from loaders.db import quarantine_failed_file
        quarantine_failed_file("SINAVIMO_API", str(e))

    # 3C. AAPRESID insect map records
    aapresid_records = []
    try:
        logger.info("Extracting AAPRESID insect map records...")
        aapresid_watermark = get_etl_watermark("AAPRESID")
        logger.info(f"AAPRESID ETL watermark: {aapresid_watermark}")
        
        seasons = ["2023/2024"] if test_mode else ["2023/2024", "2021/2022", "2019/2020"]
        fetched_aapresid = extract_aapresid_data(seasons=seasons)
        if test_mode and fetched_aapresid:
            logger.info("Test mode: limiting AAPRESID records to 5.")
            fetched_aapresid = fetched_aapresid[:5]
        if fetched_aapresid:
            if aapresid_watermark:
                fetched_aapresid = [r for r in fetched_aapresid if r.occurrence_date.replace(tzinfo=None) > aapresid_watermark.replace(tzinfo=None)]
            if fetched_aapresid:
                # Quality Gate Check
                df_aapresid = pd.DataFrame([r.dict() for r in fetched_aapresid])
                validate_pest_records_dataframe(df_aapresid)
                
                ingest_pest_records(fetched_aapresid)
                aapresid_records.extend(fetched_aapresid)
                latest_aapresid_date = max(r.occurrence_date for r in fetched_aapresid)
                update_etl_watermark("AAPRESID", latest_aapresid_date)
    except Exception as e:
        logger.error(f"Failed to fetch/load AAPRESID map data: {e}")
        from loaders.db import quarantine_failed_file
        quarantine_failed_file("AAPRESID_API", str(e))

    # 3D. PowerBI dashboard records
    pbi_records = []
    try:
        logger.info("Extracting PowerBI dashboard records...")
        pbi_watermark = get_etl_watermark("PowerBI")
        logger.info(f"PowerBI ETL watermark: {pbi_watermark}")
        
        from extractors.powerbi_maiz import extract_powerbi_data
        pbi_limit = 5 if test_mode else None
        fetched_pbi = extract_powerbi_data(limit=pbi_limit)
        if fetched_pbi:
            if pbi_watermark:
                fetched_pbi = [r for r in fetched_pbi if r.occurrence_date.replace(tzinfo=None) > pbi_watermark.replace(tzinfo=None)]
            if fetched_pbi:
                # Quality Gate Check
                df_pbi = pd.DataFrame([r.dict() for r in fetched_pbi])
                validate_pest_records_dataframe(df_pbi)
                
                ingest_pest_records(fetched_pbi)
                pbi_records.extend(fetched_pbi)
                latest_pbi_date = max(r.occurrence_date for r in fetched_pbi)
                update_etl_watermark("PowerBI", latest_pbi_date)
    except Exception as e:
        logger.error(f"Failed to fetch/load PowerBI dashboard data: {e}")
        from loaders.db import quarantine_failed_file
        quarantine_failed_file("PowerBI_API", str(e))

    # 3E. AAPPCE Red MIP/TDF PDF reports
    aappce_records = []
    try:
        logger.info("Extracting AAPPCE PDF report records...")
        aappce_watermark = get_etl_watermark("AAPPCE")
        logger.info(f"AAPPCE ETL watermark: {aappce_watermark}")
        
        aappce_limit = 1 if test_mode else None
        fetched_aappce = extract_aappce_data(limit_reports=aappce_limit)
        if fetched_aappce:
            if aappce_watermark:
                fetched_aappce = [r for r in fetched_aappce if r.occurrence_date.replace(tzinfo=None) > aappce_watermark.replace(tzinfo=None)]
            if fetched_aappce:
                # Quality Gate Check
                df_aappce = pd.DataFrame([r.dict() for r in fetched_aappce])
                validate_pest_records_dataframe(df_aappce)
                
                ingest_pest_records(fetched_aappce)
                aappce_records.extend(fetched_aappce)
                latest_aappce_date = max(r.occurrence_date for r in fetched_aappce)
                update_etl_watermark("AAPPCE", latest_aappce_date)
    except Exception as e:
        logger.error(f"Failed to fetch/load AAPPCE report data: {e}")
        from loaders.db import quarantine_failed_file
        quarantine_failed_file("AAPPCE_API", str(e))

    # Combine all biological records for unified climate harvesting
    all_pest_records = all_maizar_records + gbif_records + sinavimo_records + aapresid_records + pbi_records + aappce_records

    # Step 4: Weather extraction from NASA POWER for each unique combined coordinate and occurrence date
    if all_pest_records:
        logger.info("Step 3: Harvesting agrometeorological daily climate telemetry from NASA POWER for all unified records...")
        
        # Load existing climate records to avoid redundant API queries and database inserts
        existing_keys = set()
        try:
            from sqlalchemy import text
            engine = get_engine()
            with engine.connect() as conn:
                res = conn.execute(text("SELECT DISTINCT time, location_id FROM climate_telemetry"))
                for row in res:
                    dt = row[0]
                    loc_id = row[1]
                    if dt and loc_id:
                        d_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
                        existing_keys.add((loc_id, d_str))
            logger.info(f"Loaded {len(existing_keys)} existing climate records from database to optimize queries.")
        except Exception as e:
            logger.warning(f"Could not load existing climate keys from database: {e}. Processing all.")

        # Extract unique combination of (latitude, longitude, date)
        unique_coord_dates = set(
            (rec.latitude, rec.longitude, rec.occurrence_date)
            for rec in all_pest_records
            if rec.latitude != 0.0 and rec.latitude is not None and rec.longitude is not None
        )
        
        # Filter unique coord dates to ONLY those that do not already exist in the database
        filtered_coord_dates = []
        for lat, lon, occ_date in unique_coord_dates:
            loc_id = f"{lat:.4f}_{lon:.4f}"
            occ_date_str = occ_date.strftime("%Y-%m-%d")
            if (loc_id, occ_date_str) not in existing_keys:
                filtered_coord_dates.append((lat, lon, occ_date))
                
        logger.info(
            f"Found {len(unique_coord_dates)} unique spatial-temporal coordinates. "
            f"Filtered out {len(unique_coord_dates) - len(filtered_coord_dates)} cached coordinate-dates. "
            f"Will harvest weather for remaining {len(filtered_coord_dates)} coordinates."
        )
        
        # Group unique coordinates to fetch their full min-max date ranges in a single API query
        from collections import defaultdict
        coord_groups = defaultdict(list)
        for lat, lon, occ_date in filtered_coord_dates:
            coord_groups[(lat, lon)].append(occ_date)
            
        logger.info(
            f"Grouped {len(filtered_coord_dates)} coordinate-dates into {len(coord_groups)} unique location range queries."
        )
        
        climate_records = []
        max_workers = 5
        logger.info(f"Initiating multithreaded weather harvesting using {max_workers} worker threads...")

        def fetch_weather_task(args_tuple):
            idx, (lat, lon), dates = args_tuple
            min_date = min(dates)
            max_date = max(dates)
            
            start_date_str = (min_date - timedelta(days=9)).strftime("%Y-%m-%d")
            end_date_str = max_date.strftime("%Y-%m-%d")
            
            try:
                try:
                    weather_recs = extract_nasa_climate(lat, lon, start_date_str, end_date_str)
                except Exception as ex_nasa:
                    logger.warning(f"NASA POWER extraction failed for ({lat:.4f}, {lon:.4f}): {ex_nasa}. Triggering fail-over to Open-Meteo...")
                    weather_recs = extract_openmeteo_climate(lat, lon, start_date_str, end_date_str)

                # Deduplicate returned daily records in-memory using loaded database keys to avoid redundant SQL inserts
                filtered_recs = [
                    rec for rec in weather_recs
                    if (rec.location_id, rec.time.strftime("%Y-%m-%d") if hasattr(rec.time, "strftime") else str(rec.time)[:10]) not in existing_keys
                ]
                return filtered_recs
            except Exception as e:
                logger.error(
                    f"Failed to fetch climate range for ({lat:.4f}, {lon:.4f}) "
                    f"from {start_date_str} to {end_date_str} (both NASA and Open-Meteo failed): {e}"
                )
                return []

        # Prepare tasks
        tasks = [(idx, coords, dates) for idx, (coords, dates) in enumerate(coord_groups.items())]

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Map tasks to thread pool
            futures = [executor.submit(fetch_weather_task, t) for t in tasks]
            
            for idx, future in enumerate(concurrent.futures.as_completed(futures)):
                recs = future.result()
                if recs:
                    climate_records.extend(recs)
                    
                # Report progress
                if (idx + 1) % 10 == 0 or (idx + 1) == len(tasks):
                    logger.info(f"Progress: [{idx+1}/{len(tasks)}] weather location ranges processed.")
                    
                # Ingest in smaller chunks of ~500 weather metrics to prevent Postgres OOM connection drops
                if len(climate_records) >= 500:
                    logger.info(f"Ingesting {len(climate_records)} weather metrics into climate_telemetry table...")
                    try:
                        ingest_climate_telemetry(climate_records, fast=True)
                        climate_records = []
                    except Exception as e:
                        logger.error(f"Failed to ingest climate variables batch: {e}")

        # Ingest remaining climate records
        if climate_records:
            logger.info(f"Ingesting remaining {len(climate_records)} weather metrics into climate_telemetry...")
            try:
                ingest_climate_telemetry(climate_records, fast=True)
            except Exception as e:
                logger.error(f"Failed to ingest remaining climate variables: {e}")

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
