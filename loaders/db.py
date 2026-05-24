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
DB_URL = os.environ.get("PLAGOUT_DB_URL")

if not DB_URL:
    logger.warning(
        "PLAGOUT_DB_URL environment variable is not set! "
        f"Falling back to default local URL: {DEFAULT_DB_URL}"
    )
    DB_URL = DEFAULT_DB_URL

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
    Ensure the database schema has the required tables, hypertables, columns and indexes.
    Executes loaders/schema.sql first to ensure tables exist, then executes the column-level migrations.
    """
    engine = get_engine()
    
    # 1. Execute schema.sql safely
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if os.path.exists(schema_path):
        logger.info(f"Loading initial schema definitions from {schema_path}...")
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            
            # Split queries by semicolon to execute them cleanly one by one
            queries = [q.strip() for q in schema_sql.split(";") if q.strip()]
            
            with engine.begin() as conn:
                for q in queries:
                    # Ignore single-line or block comments
                    if q.startswith("--"):
                        continue
                    conn.execute(text(q))
            logger.info("Database schema initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to execute database schema initialization: {e}")
            raise
    else:
        logger.warning(f"Schema file not found at {schema_path}. Skipping initial schema DDL.")

    # 2. Run migrations
    alter_queries = [
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS institution TEXT;",
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS province TEXT;",
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS locality TEXT;",
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS adults_count INT;",
        "ALTER TABLE pest_monitoring ADD COLUMN IF NOT EXISTS infection_percent FLOAT;",
        "CREATE INDEX IF NOT EXISTS pest_monitoring_lookup_idx ON pest_monitoring(occurrence_date, pest_type, province, locality, institution);",
        "CREATE INDEX IF NOT EXISTS climate_telemetry_lookup_idx ON climate_telemetry(time, location_id);"
    ]
    
    with engine.begin() as conn:
        for query in alter_queries:
            try:
                conn.execute(text(query))
                logger.info(f"Executed migration query: {query.strip()}")
            except Exception as e:
                # If there's an issue executing, log and continue (e.g. columns/indexes might already exist)
                logger.warning(f"Failed to execute migration query: {e}")

