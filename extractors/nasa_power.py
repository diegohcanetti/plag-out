"""
NASA POWER Climate Data Extractor

This module fetches historical agrometeorological variables from the NASA POWER API.
It implements robust caching and retry mechanics, parsing the JSON responses into
validated Pydantic models ready for ingestion.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
import requests
import requests_cache
from retry_requests import retry
from models.schemas import ClimateTelemetryRecord

logger = logging.getLogger(__name__)

# Configure local SQLite cache for NASA POWER calls
requests_cache.install_cache(
    ".nasa_power_cache",
    expire_after=-1  # Static historical weather data does not change, never expire
)


class NasaPowerExtractor:
    """
    Client for the NASA POWER API implementing resilient daily data extraction.
    """
    def __init__(self, retries: int = 5, backoff_factor: float = 0.3) -> None:
        # Wrap requests with automatic retries on status codes / connection drops
        session = requests.Session()
        self.session = retry(session, retries=retries, backoff_factor=backoff_factor)

    def extract(
        self,
        latitude: float,
        longitude: float,
        start_date: str,  # format YYYY-MM-DD
        end_date: str,    # format YYYY-MM-DD
    ) -> List[ClimateTelemetryRecord]:
        """
        Queries NASA POWER point API and parses parameters into ClimateTelemetryRecord schemas.
        """
        # Convert dates to YYYYMMDD
        start_str = start_date.replace("-", "")
        end_str = end_date.replace("-", "")
        
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start": start_str,
            "end": end_str,
            "parameters": "T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOT",
            "community": "AG",
            "format": "JSON"
        }
        
        logger.info(
            f"Querying NASA POWER API for coords ({latitude}, {longitude}) "
            f"from {start_date} to {end_date}"
        )
        
        headers = {
            "User-Agent": "Plag-out-Agrotech-Thesis-Pipeline-MVP/1.0"
        }
        
        response = self.session.get(url, params=params, headers=headers, timeout=25)
        response.raise_for_status()
        
        data = response.json()
        
        # Verify JSON schema is valid
        if "properties" not in data or "parameter" not in data["properties"]:
            logger.error(f"NASA POWER API returned invalid properties structure: {list(data.keys())}")
            return []
            
        parameters_data = data["properties"]["parameter"]
        
        # Ensure we have all requested keys
        required_keys = ["T2M", "T2M_MAX", "T2M_MIN", "RH2M"]
        for key in required_keys:
            if key not in parameters_data:
                logger.error(f"NASA POWER response missing expected parameter: {key}")
                return []
                
        # Precipitation could be named PRECTOT or PRECTOTCORR in the response
        precip_key = "PRECTOTCORR" if "PRECTOTCORR" in parameters_data else "PRECTOT"
        if precip_key not in parameters_data:
            logger.error("NASA POWER response missing expected parameter for precipitation (PRECTOT/PRECTOTCORR)")
            return []
                
        # Reconstruct time-series records
        records = []
        location_id = f"{latitude:.4f}_{longitude:.4f}"
        
        # Pull keys from one of the datasets to get all date strings
        date_keys = list(parameters_data["T2M"].keys())
        
        for date_str in date_keys:
            # Parse date YYYYMMDD
            try:
                date_val = datetime.strptime(date_str, "%Y%m%d")
            except Exception as e:
                logger.warning(f"Failed to parse date string {date_str}: {e}")
                continue
                
            # Check values
            temp_mean = parameters_data["T2M"][date_str]
            temp_max = parameters_data["T2M_MAX"][date_str]
            temp_min = parameters_data["T2M_MIN"][date_str]
            humidity = parameters_data["RH2M"][date_str]
            precipitation = parameters_data[precip_key][date_str]
            
            # NASA POWER uses -999.0 or -99.0 or -9999.0 to signify missing data
            def filter_missing(val):
                if val is None or val in [-999.0, -99.0, -9999.0]:
                    return None
                return float(val)

            rec = ClimateTelemetryRecord(
                time=date_val,
                location_id=location_id,
                temp_max=filter_missing(temp_max),
                humidity=filter_missing(humidity),
                precipitation=filter_missing(precipitation),
                latitude=latitude,
                longitude=longitude
            )
            records.append(rec)
            
        logger.info(f"Successfully extracted {len(records)} daily climate records from NASA POWER.")
        return records


def extract_nasa_climate(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str
) -> List[ClimateTelemetryRecord]:
    """
    Functional entrypoint to retrieve historical weather telemetry.
    """
    extractor = NasaPowerExtractor()
    return extractor.extract(latitude, longitude, start_date, end_date)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test Pergamino, Buenos Aires coordinates
    recs = extract_nasa_climate(-33.8899, -60.5696, "2024-01-01", "2024-01-05")
    print(f"Extracted {len(recs)} test records. Sample:")
    for r in recs[:2]:
        print(r)
