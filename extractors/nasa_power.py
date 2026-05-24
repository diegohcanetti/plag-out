"""
NASA POWER Climate Data Extractor

This module fetches historical agrometeorological variables from the NASA POWER API.
It implements robust caching and retry mechanics, parsing the JSON responses into
validated Pydantic models ready for ingestion.
"""

import logging
import time
import socket
from datetime import datetime
from typing import List, Dict, Optional
import requests
import requests_cache
from retry_requests import retry
from models.schemas import ClimateTelemetryRecord

logger = logging.getLogger(__name__)

# Production-grade DNS caching at the Python socket level to completely prevent NameResolutionError (DNS exhaustion)
_DNS_CACHE = {}
_ORIGINAL_GETADDRINFO = socket.getaddrinfo
def _cached_getaddrinfo(*args, **kwargs):
    # Unify positional and keyword arguments into a standard tuple key
    host = args[0] if len(args) > 0 else kwargs.get("host")
    port = args[1] if len(args) > 1 else kwargs.get("port")
    family = args[2] if len(args) > 2 else kwargs.get("family", 0)
    socket_type = args[3] if len(args) > 3 else kwargs.get("type", 0)
    proto = args[4] if len(args) > 4 else kwargs.get("proto", 0)
    flags = args[5] if len(args) > 5 else kwargs.get("flags", 0)

    cache_key = (host, port, family, socket_type, proto, flags)

    if cache_key in _DNS_CACHE:
        return _DNS_CACHE[cache_key]
    try:
        res = _ORIGINAL_GETADDRINFO(*args, **kwargs)
        _DNS_CACHE[cache_key] = res
        return res
    except Exception as e:
        # Fallback check matches only the host string
        for cached_key, cached_res in _DNS_CACHE.items():
            if host and cached_key[0] == host:
                logger.warning(f"DNS lookup failed for {host}. Using cached fallback IP: {cached_res}")
                return cached_res
        raise e

socket.getaddrinfo = _cached_getaddrinfo

# Configure local SQLite cache for NASA POWER calls
requests_cache.install_cache(
    ".nasa_power_cache",
    expire_after=-1  # Static historical weather data does not change, never expire
)

# Global tracker for non-cached network calls to facilitate rate limiting / micro-pacing
_NETWORK_CALLS_COUNT = 0


class NasaPowerExtractor:
    """
    Client for the NASA POWER API implementing resilient daily data extraction.
    """
    def __init__(self, retries: int = 5, backoff_factor: float = 1.0) -> None:
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
        
        global _NETWORK_CALLS_COUNT
        
        max_attempts = 3
        response = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=25)
                response.raise_for_status()
                break  # Success!
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ce:
                if attempt == max_attempts:
                    logger.error(f"Failed to fetch climate variables for ({latitude}, {longitude}) after {max_attempts} attempts due to network errors.")
                    raise ce
                logger.warning(
                    f"Network/DNS error on attempt {attempt}/{max_attempts} for coords ({latitude}, {longitude}): {ce}. "
                    f"Initiating a 30-second cooldown recovery sleep before retry..."
                )
                time.sleep(30.0)
            except Exception as e:
                logger.error(f"Fatal or unexpected error querying NASA POWER on attempt {attempt}/{max_attempts}: {e}")
                raise e
                
        if response is None:
            return []
            
        # Inspect caching status to apply smart pacing (avoid slowing down cache hits)
        is_from_cache = getattr(response, "from_cache", False)
        if not is_from_cache:
            _NETWORK_CALLS_COUNT += 1
            logger.info(f"NASA POWER API network call #{_NETWORK_CALLS_COUNT}. Applying 0.3s micro-pacing sleep...")
            time.sleep(0.3)
            
            # Group requests into chunks of 100, followed by a cool-down sleep
            if _NETWORK_CALLS_COUNT % 100 == 0:
                logger.info(f"Reached {_NETWORK_CALLS_COUNT} non-cached API requests. Initiating a 15-second chunk cool-down sleep...")
                time.sleep(15.0)
        else:
            logger.debug(f"NASA POWER cache hit for coords ({latitude}, {longitude}) from {start_date} to {end_date}.")
        
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


# Cached single global instance of NasaPowerExtractor to leverage HTTP Keep-Alive connection pooling
_SHARED_EXTRACTOR = None


def extract_nasa_climate(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    extractor: Optional[NasaPowerExtractor] = None
) -> List[ClimateTelemetryRecord]:
    """
    Functional entrypoint to retrieve historical weather telemetry.
    Reuses a shared/provided NasaPowerExtractor to leverage HTTP Keep-Alive connection pooling.
    """
    global _SHARED_EXTRACTOR
    if extractor is None:
        if _SHARED_EXTRACTOR is None:
            _SHARED_EXTRACTOR = NasaPowerExtractor()
        extractor = _SHARED_EXTRACTOR
    return extractor.extract(latitude, longitude, start_date, end_date)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test Pergamino, Buenos Aires coordinates
    recs = extract_nasa_climate(-33.8899, -60.5696, "2024-01-01", "2024-01-05")
    print(f"Extracted {len(recs)} test records. Sample:")
    for r in recs[:2]:
        print(r)
