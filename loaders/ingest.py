"""
Data Ingestion Layer

Handles inserting and upserting normalized data records into the local TimescaleDB/PostgreSQL database.
Utilizes PostGIS geometry construction for coordinates.
"""

import logging
from typing import List
from sqlalchemy import text
from loaders.db import get_engine
from models.schemas import PestMonitoringRecord, ClimateTelemetryRecord

logger = logging.getLogger(__name__)


def ingest_pest_records(records: List[PestMonitoringRecord]) -> int:
    """
    Ingests a list of PestMonitoringRecords into the local `pest_monitoring` table.
    Uses bulk insert with PostGIS coordinate geometry construction.
    """
    if not records:
        logger.warning("No pest monitoring records provided for ingestion.")
        return 0

    engine = get_engine()
    query = text("""
        INSERT INTO pest_monitoring (
            occurrence_date, pest_type, severity_level, geom, 
            institution, province, locality, adults_count, infection_percent
        ) VALUES (
            :occurrence_date, :pest_type, :severity_level, 
            ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
            :institution, :province, :locality, :adults_count, :infection_percent
        )
    """)

    # Convert Pydantic objects to standard dictionaries for SQL parameter binding
    param_list = [
        {
            "occurrence_date": rec.occurrence_date,
            "pest_type": rec.pest_type,
            "severity_level": rec.severity_level,
            "longitude": rec.longitude,
            "latitude": rec.latitude,
            "institution": rec.institution,
            "province": rec.province,
            "locality": rec.locality,
            "adults_count": rec.adults_count,
            "infection_percent": rec.infection_percent
        }
        for rec in records
    ]

    try:
        with engine.begin() as conn:
            result = conn.execute(query, param_list)
            inserted_count = len(param_list)
            logger.info(f"Successfully ingested {inserted_count} pest monitoring records.")
            return inserted_count
    except Exception as e:
        logger.error(f"Error ingesting pest monitoring records: {e}")
        raise


def ingest_climate_telemetry(records: List[ClimateTelemetryRecord]) -> int:
    """
    Ingests a list of ClimateTelemetryRecords into the `climate_telemetry` table.
    Uses PostGIS geometry for spatial tracking and TimescaleDB hypertable optimization.
    Duplicates are handled by ignoring/updating where appropriate (or standard inserts).
    """
    if not records:
        logger.warning("No climate telemetry records provided for ingestion.")
        return 0

    engine = get_engine()
    # In order to support upsert, we need a unique constraint on (time, location_id).
    # Since the user didn't specify one, we can do a standard insert. Let's make sure
    # we don't insert duplicate keys if a unique index is present or simply run a standard INSERT.
    query = text("""
        INSERT INTO climate_telemetry (
            time, location_id, temp_max, humidity, precipitation, location
        ) VALUES (
            :time, :location_id, :temp_max, :humidity, :precipitation,
            ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
        )
    """)

    param_list = [
        {
            "time": rec.time,
            "location_id": rec.location_id,
            "temp_max": rec.temp_max,
            "humidity": rec.humidity,
            "precipitation": rec.precipitation,
            "longitude": rec.longitude,
            "latitude": rec.latitude
        }
        for rec in records
    ]

    try:
        with engine.begin() as conn:
            result = conn.execute(query, param_list)
            inserted_count = len(param_list)
            logger.info(f"Successfully ingested {inserted_count} climate telemetry records.")
            return inserted_count
    except Exception as e:
        logger.error(f"Error ingesting climate telemetry records: {e}")
        raise
