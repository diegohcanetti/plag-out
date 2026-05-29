# gdd_service.py
"""
GDD (Growing Degree Days) Service

This module calculates degree-days and simulates crop/pest development progress
by querying agrometeorological data from the Open-Meteo Archive API.
Ported and unified from rami-nava/PLAG-OUT pf-backend.
"""

import logging
import requests
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# --- Models ---

class WeatherData(BaseModel):
    date: date
    temp_max: float
    temp_min: float
    
    @property
    def average_temp(self) -> float:
        return (self.temp_max + self.temp_min) / 2.0


class GDDSimulationRequest(BaseModel):
    latitude: float
    longitude: float
    startDate: str 
    currentDate: str 
    initialGDD: int 
    targetGDD: int 
    baseTemperature: float 
    cropName: str 
    notes: Optional[str] = None


class GDDSimulationResponse(BaseModel):
    current_gdd: int
    target_gdd: int
    progress_percentage: float
    date: str
    avg_temp: float
    gdd_gained: float
    target_reached: bool
    message: str


# --- GDD Calculator Service ---

class GDDCalculatorService:
    """
    Calculates Growing Degree Days (GDD) using the formula:
    GDD = ((Tmax + Tmin) / 2) - Tbase
    If the result is negative, it returns 0.0.
    """
    def calculate_daily_gdd(self, weather_data: WeatherData, base_temperature: float) -> float:
        """Calculates GDD for a single day"""
        if weather_data is None:
            return 0.0
        
        avg_temp = weather_data.average_temp
        gdd = avg_temp - base_temperature
        
        return max(gdd, 0.0)


# --- Weather Service ---

class WeatherService:
    OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
    
    def get_weather_for_date(self, latitude: float, longitude: float, current_date: date) -> Optional[WeatherData]:
        """Fetches historical max and min temperature for a specific coordinate and date from Open-Meteo."""
        try:
            url = (
                f"{self.OPEN_METEO_URL}"
                f"?latitude={latitude:.4f}"
                f"&longitude={longitude:.4f}"
                f"&start_date={current_date}"
                f"&end_date={current_date}"
                f"&daily=temperature_2m_max,temperature_2m_min"
                f"&timezone=auto"
            )
            
            logger.info(f"[GDD-WEATHER] Requesting: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"[GDD-WEATHER] Response: {data}")
            
            if 'daily' not in data:
                logger.warning("[GDD-WEATHER] 'daily' missing in response")
                return None
            
            daily = data['daily']
            temps_max = daily.get('temperature_2m_max')
            temps_min = daily.get('temperature_2m_min')
            
            if not temps_max or not temps_min or len(temps_max) == 0 or len(temps_min) == 0:
                logger.warning("[GDD-WEATHER] Empty temperature arrays in response")
                return None
            
            temp_max_value = float(temps_max[0])
            temp_min_value = float(temps_min[0])
            
            weather = WeatherData(
                date=current_date,
                temp_max=temp_max_value,
                temp_min=temp_min_value
            )
            logger.info(f"[GDD-WEATHER] WeatherData constructed: {weather}")
            return weather
            
        except requests.exceptions.Timeout:
            logger.error("[GDD-WEATHER] Request timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"[GDD-WEATHER] HTTP request error: {e}")
            return None
        except Exception as e:
            logger.error(f"[GDD-WEATHER] General error: {e}")
            return None
