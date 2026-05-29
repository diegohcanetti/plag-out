"""
Open-Meteo Historical Climate Data Extractor

This module fetches historical agrometeorological variables from the Open-Meteo Archive API.
It serves as a highly reliable, rate-limit-friendly fallback for NASA POWER API.
"""

import logging
import requests
from datetime import datetime
from typing import List, Optional
from models.schemas import ClimateTelemetryRecord

logger = logging.getLogger(__name__)

OPENMETEO_API_URL = "https://archive-api.open-meteo.com/v1/archive"


class OpenMeteoExtractor:
    """
    Client for the Open-Meteo Archive API implementing resilient daily data extraction.
    """
    def __init__(self, timeout: int = 25) -> None:
        self.timeout = timeout

    def extract(
        self,
        latitude: float,
        longitude: float,
        start_date: str,  # format YYYY-MM-DD
        end_date: str,    # format YYYY-MM-DD
    ) -> List[ClimateTelemetryRecord]:
        """
        Queries Open-Meteo Archive API and parses parameters into ClimateTelemetryRecord schemas.
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,relative_humidity_2m_mean,precipitation",
            "timezone": "America/Argentina/Buenos_Aires"
        }

        logger.info(
            f"Querying Open-Meteo Archive API for coords ({latitude}, {longitude}) "
            f"from {start_date} to {end_date}"
        )

        try:
            response = requests.get(OPENMETEO_API_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to query Open-Meteo API: {e}")
            raise e

        if "daily" not in data:
            logger.error(f"Open-Meteo response missing daily data: {data}")
            return []

        daily = data["daily"]
        times = daily.get("time", [])
        temp_maxs = daily.get("temperature_2m_max", [])
        humidities = daily.get("relative_humidity_2m_mean", [])
        precipitations = daily.get("precipitation", [])

        records = []
        location_id = f"{latitude:.4f}_{longitude:.4f}"

        for idx, date_str in enumerate(times):
            try:
                date_val = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Failed to parse date string {date_str}: {e}")
                continue

            temp_max = temp_maxs[idx] if idx < len(temp_maxs) else None
            humidity = humidities[idx] if idx < len(humidities) else None
            precipitation = precipitations[idx] if idx < len(precipitations) else None

            # Enforce float typing and filter None values
            def to_float(val):
                return float(val) if val is not None else None

            rec = ClimateTelemetryRecord(
                time=date_val,
                location_id=location_id,
                temp_max=to_float(temp_max),
                humidity=to_float(humidity),
                precipitation=to_float(precipitation),
                latitude=latitude,
                longitude=longitude
            )
            records.append(rec)

        logger.info(f"Successfully extracted {len(records)} daily climate records from Open-Meteo.")
        return records


def extract_openmeteo_climate(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> List[ClimateTelemetryRecord]:
    """
    Functional entrypoint to retrieve historical weather telemetry from Open-Meteo.
    """
    extractor = OpenMeteoExtractor()
    return extractor.extract(latitude, longitude, start_date, end_date)
