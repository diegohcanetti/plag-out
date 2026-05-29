CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS climate_telemetry (
    time TIMESTAMPTZ NOT NULL,
    location_id TEXT NOT NULL,
    temp_max FLOAT,
    humidity FLOAT,
    precipitation FLOAT,
    location GEOGRAPHY(POINT)
);

CREATE TABLE IF NOT EXISTS pest_monitoring (
    id SERIAL PRIMARY KEY,
    occurrence_date TIMESTAMPTZ NOT NULL,
    pest_type TEXT,
    severity_level TEXT,
    geom GEOGRAPHY(POINT) NOT NULL,
    institution TEXT,
    province TEXT,
    locality TEXT,
    adults_count INTEGER,
    infection_percent FLOAT
);

CREATE INDEX IF NOT EXISTS pest_geom_idx ON pest_monitoring USING GIST (geom);

CREATE TABLE IF NOT EXISTS etl_watermarks (
    source_name TEXT PRIMARY KEY,
    last_run_timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_quarantine (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    error_message TEXT,
    quarantined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

