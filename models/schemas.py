"""
Data Models and Schemas

Defines the core domain models using Pydantic for validation, parsing, and type hinting.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PestMonitoringRecord(BaseModel):
    """
    Schema representing a biological pest occurrence record (e.g. from MAIZAR or SINAVIMO).
    """
    occurrence_date: datetime
    pest_type: str = Field(..., description="Species name, e.g., Dalbulus maidis or Spodoptera frugiperda")
    severity_level: str = Field(..., description="Qualitative severity level (Low, Medium, High, etc.)")
    latitude: float
    longitude: float
    institution: Optional[str] = None
    province: Optional[str] = None
    locality: Optional[str] = None
    adults_count: Optional[int] = None
    infection_percent: Optional[float] = None


class ClimateTelemetryRecord(BaseModel):
    """
    Schema representing a weather telemetry reading (e.g. from NASA POWER or GEE).
    """
    time: datetime
    location_id: str = Field(..., description="Unique identifier for location, e.g. 'lat_lon'")
    temp_max: Optional[float] = None
    humidity: Optional[float] = None
    precipitation: Optional[float] = None
    latitude: float
    longitude: float
