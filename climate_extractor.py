"""
Climate Data Extraction Layer

This module handles the extraction of historical weather data from the Open-Meteo Archive API.
It is designed to be highly modular, decoupled from any downstream transformation or database loading logic,
making it suitable for orchestration by a master pipeline script.

Libraries used:
- openmeteo-requests
- requests-cache
- retry-requests
- pandas
"""

import logging
from typing import List, Optional
import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

# Initialize logger for this module
logger = logging.getLogger(__name__)


class ClimateExtractor:
    """
    A robust extractor class for pulling historical weather data from Open-Meteo.

    Implements local request caching and resilient retry mechanisms to efficiently
    retrieve daily climate variables without exhausting API limits.
    """

    def __init__(
        self,
        cache_name: str = ".climate_cache",
        expire_after: int = -1,
        retries: int = 5,
        backoff_factor: float = 0.2,
    ) -> None:
        """
        Initialize the ClimateExtractor with a resilient Open-Meteo API client.

        Args:
            cache_name (str): Path/prefix for the local SQLite cache file.
            expire_after (int): Cache expiration in seconds. Defaults to -1 (never expire)
                                since historical weather archive data is static.
            retries (int): Number of automatic retries for transient API failures.
            backoff_factor (float): Exponential backoff factor applied between retries.
        """
        self.cache_name = cache_name
        self.expire_after = expire_after
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.client = self._setup_client()

    def _setup_client(self) -> openmeteo_requests.Client:
        """
        Configure and return the Open-Meteo client wrapped with caching and retry sessions.

        Returns:
            openmeteo_requests.Client: Configured API client.
        """
        # Setup caching session to store API responses locally
        cache_session = requests_cache.CachedSession(
            self.cache_name, expire_after=self.expire_after
        )
        # Wrap the cached session with automatic retries on status errors/timeouts
        retry_session = retry(
            cache_session, retries=self.retries, backoff_factor=self.backoff_factor
        )
        return openmeteo_requests.Client(session=retry_session)

    def extract(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        timezone: str = "auto",
    ) -> pd.DataFrame:
        """
        Extract daily historical weather features for a given geographic location and date range.

        Features extracted and their corresponding DataFrame columns:
        - Maximum daily temperature -> 'temperatura_max'
        - Average relative humidity -> 'humedad_relativa'
        - Accumulated daily precipitation -> 'precipitacion_7dias'
          (Note: Fetches raw daily precipitation for now. The 7-day rolling sum logic
           is deliberately deferred to the downstream transformation layer).

        Args:
            latitude (float): Latitude of the target region.
            longitude (float): Longitude of the target region.
            start_date (str): Start date in 'YYYY-MM-DD' format.
            end_date (str): End date in 'YYYY-MM-DD' format.
            timezone (str): Timezone for aligning daily aggregations. Defaults to 'auto'.

        Returns:
            pd.DataFrame: A clean Pandas DataFrame containing the extracted daily features.
        """
        url = "https://archive-api.open-meteo.com/v1/archive"

        # Define requested variables in exact order to ensure correct indexing below
        daily_variables: List[str] = [
            "temperature_2m_max",
            "relative_humidity_2m_mean",
            "precipitation_sum",
        ]

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "daily": daily_variables,
            "timezone": timezone,
        }

        logger.info(
            f"Querying Open-Meteo Archive API for coordinates ({latitude}, {longitude}) "
            f"from {start_date} to {end_date}."
        )

        # Execute API request
        responses = self.client.weather_api(url, params=params)

        # Process the single requested location response
        response = responses[0]
        daily = response.Daily()

        # Extract features as flat NumPy arrays using strict variable indices
        temp_max = daily.Variables(0).ValuesAsNumpy()
        humidity_mean = daily.Variables(1).ValuesAsNumpy()
        precip_sum = daily.Variables(2).ValuesAsNumpy()

        # Construct date range array corresponding to the flatbuffer response intervals
        date_range = pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left",
        )

        # Assemble the structured clean DataFrame
        df = pd.DataFrame(
            {
                "fecha": date_range.date,
                "temperatura_max": temp_max,
                "humedad_relativa": humidity_mean,
                "precipitacion_7dias": precip_sum,
            }
        )

        logger.info(f"Successfully extracted {len(df)} daily records.")
        return df


def extract_climate_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    cache_name: Optional[str] = ".climate_cache",
) -> pd.DataFrame:
    """
    Convenience functional interface to extract historical weather data.

    Instantiates the ClimateExtractor class and triggers extraction. Useful for simple scripts
    or direct pipeline orchestration calls.

    Args:
        latitude (float): Latitude of the target region.
        longitude (float): Longitude of the target region.
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
        cache_name (Optional[str]): Custom cache DB name/path. Defaults to '.climate_cache'.

    Returns:
        pd.DataFrame: Clean Pandas DataFrame with extracted daily climate features.
    """
    extractor = ClimateExtractor(
        cache_name=cache_name if cache_name else ".climate_cache"
    )
    return extractor.extract(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
    )


if __name__ == "__main__":
    # Setup standard output logging for local execution/testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Test parameters: Agricultural core region in Pergamino, Buenos Aires Province, Argentina
    TEST_LAT = -33.8899
    TEST_LON = -60.5696
    TEST_START = "2024-01-01"
    TEST_END = "2024-01-31"

    print("=" * 70)
    print(
        f"Testing ClimateExtractor for Pergamino, Buenos Aires ({TEST_LAT}, {TEST_LON})"
    )
    print(f"Period: {TEST_START} to {TEST_END}")
    print("=" * 70)

    # Perform extraction
    df_climate = extract_climate_data(
        latitude=TEST_LAT,
        longitude=TEST_LON,
        start_date=TEST_START,
        end_date=TEST_END,
    )

    print("\nExtraction Complete. Displaying DataFrame head:")
    print("-" * 70)
    print(df_climate.head())
    print("-" * 70)
    print(f"Total Rows Extracted: {len(df_climate)}")
    print(f"Columns: {list(df_climate.columns)}")
