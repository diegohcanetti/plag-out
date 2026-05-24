-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 1. Create climate telemetry table
CREATE TABLE IF NOT EXISTS climate_telemetry (
    time TIMESTAMPTZ NOT NULL,
    location_id TEXT NOT NULL,
    temp_max FLOAT,
    humidity FLOAT,
    precipitation FLOAT,
    location GEOGRAPHY(POINT)
);

-- 2. Convert to TimescaleDB hypertable safely
SELECT create_hypertable('climate_telemetry', 'time', if_not_exists => TRUE);

-- 3. Create pest monitoring table
CREATE TABLE IF NOT EXISTS pest_monitoring (
    id SERIAL PRIMARY KEY,
    occurrence_date TIMESTAMPTZ NOT NULL,
    pest_type TEXT,
    severity_level TEXT,
    geom GEOGRAPHY(POINT) NOT NULL
);

-- 4. Create PostGIS spatial index
CREATE INDEX IF NOT EXISTS pest_geom_idx ON pest_monitoring USING GIST (geom);
