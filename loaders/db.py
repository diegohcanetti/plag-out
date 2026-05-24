"""
Database Connection Utility

This module establishes a connection to the local PostgreSQL database (with PostGIS and TimescaleDB).
It uses SQLAlchemy to provide a robust connection pool.
"""

import os
import logging
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

# Default connection URL. Can be overridden with PLAGOUT_DB_URL env var.
DEFAULT_DB_URL = "postgresql://localhost/plagout_db"
DB_URL = os.environ.get("PLAGOUT_DB_URL", DEFAULT_DB_URL)

_engine: Engine = None
_SessionLocal = None


def get_engine() -> Engine:
    """
    Get or create the SQLAlchemy engine instance.
    """
    global _engine
    if _engine is None:
        try:
            _engine = create_engine(
                DB_URL,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10
            )
            logger.info("SQLAlchemy database engine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise
    return _engine


def get_session() -> Session:
    """
    Get a new SQLAlchemy session. Make sure to close it after use!
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal()


def execute_migration_queries():
    """
    Ensure the database schema has the required columns and indexes for Plag-out data.
    If the tables exist, it alters them to add the MAIZAR/pest metrics and lookup indexes if missing.
    """
    alter_queries = [
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS institution TEXT;",
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS province TEXT;",
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS locality TEXT;",
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS adults_count INT;",
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS infection_percent FLOAT;",
        "CREATE INDEX IF NOT EXISTS pest_monitoring_lookup_idx ON pest_monitoring(occurrence_date, pest_type, province, locality, institution);",
        "CREATE INDEX IF NOT EXISTS climate_telemetry_lookup_idx ON climate_telemetry(time, location_id);"
    ]
    engine = get_engine()
    with engine.begin() as conn:
        for query in alter_queries:
            try:
                conn.execute(text(query))
                logger.info(f"Executed: {query.strip()}")
            except Exception as e:
                # If there's an issue executing, log and continue (e.g. columns/indexes might already exist)
                logger.warning(f"Failed to execute migration query: {e}")
