import os
import math
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.schemas import (
    HealthResponse,
    GDDHealthResponse,
    ActiveAlertsResponse,
    PestAlertItem,
    PredictionsResponse,
    GDDSimulationRequest,
    GDDSimulationResponse,
)
from gdd_service import WeatherService, GDDCalculatorService

logger = logging.getLogger("api.routes")

router = APIRouter()

# Initialize services
weather_service = WeatherService()
gdd_calculator = GDDCalculatorService()

# API Key Authentication Setup
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != settings.plagout_api_key:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Could not validate credentials: Invalid X-API-KEY header."
        )
    return api_key


# --- Helper for Fallback Haversine distance ---
def calculate_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points in kilometers.
    """
    R = 6371.0  # Earth's radius in km
    
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(d_lat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(d_lon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# --- Health Check Endpoints ---
@router.get("/api/v1/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """
    Service health check endpoint.
    """
    try:
        # Quick db check
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"
    
    return HealthResponse(status="healthy", database=db_status)


@router.get("/api/gdd/health", response_model=GDDHealthResponse)
def gdd_health_check():
    """
    Health check specifically matching Kotlin app path.
    """
    return GDDHealthResponse(status="GDD API is running")


# --- GDD Simulation Endpoints ---
@router.post("/api/gdd/simulate-day", response_model=GDDSimulationResponse)
@router.post("/api/v1/gdd/simulate-day", response_model=GDDSimulationResponse)
def simulate_day(request: GDDSimulationRequest):
    """
    Simulates GDD accumulation for a crop/pest on a given date using Open-Meteo data.
    """
    try:
        current_date = datetime.strptime(request.currentDate, '%Y-%m-%d').date()
        
        weather_data = weather_service.get_weather_for_date(
            request.latitude,
            request.longitude,
            current_date
        )
        
        if weather_data is None:
            raise HTTPException(status_code=400, detail="No weather data available for this date")
        
        daily_gdd = gdd_calculator.calculate_daily_gdd(weather_data, request.baseTemperature)
        new_gdd = request.initialGDD + int(daily_gdd)
        
        progress_percentage = min((new_gdd / request.targetGDD) * 100, 100) if request.targetGDD > 0 else 0.0
        target_reached = new_gdd >= request.targetGDD
        
        if target_reached:
            message = "¡Objetivo de GDD alcanzado! Plagas pueden estar en desarrollo"
        else:
            remaining = request.targetGDD - new_gdd
            message = f"GDD: {new_gdd}/{request.targetGDD} ({remaining} GDD restantes)"

        return GDDSimulationResponse(
            current_gdd=new_gdd,
            target_gdd=request.targetGDD,
            progress_percentage=progress_percentage,
            date=str(current_date),
            avg_temp=float(weather_data.average_temp),
            gdd_gained=float(daily_gdd),
            target_reached=target_reached,
            message=message
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GDD simulate_day endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# --- Active Alerts Endpoints ---
@router.get("/api/v1/alerts/active", response_model=ActiveAlertsResponse, dependencies=[Depends(verify_api_key)])
def active_alerts(db: Session = Depends(get_db), limit: Optional[int] = None):
    """
    Retrieves active thermodynamic pest alerts from the database.
    """
    pg_limit = limit or settings.default_pagination_limit
    alerts = []
    
    try:
        query = text(
            "SELECT species, locality, province, latitude, longitude, biofix_date, "
            "accumulated_gdd, days_active, biological_stage, recommendation, threat_level, "
            "generated_at, evaluation_date "
            "FROM pest_alerts "
            "ORDER BY evaluation_date DESC LIMIT :limit"
        )
        res = db.execute(query, {"limit": pg_limit}).fetchall()
        for row in res:
            alerts.append(PestAlertItem(
                species=row[0],
                locality=row[1],
                province=row[2],
                latitude=float(row[3]),
                longitude=float(row[4]),
                biofix_date=row[5],
                accumulated_gdd=float(row[6]),
                days_active=int(row[7]),
                biological_stage=row[8],
                recommendation=row[9],
                threat_level=row[10],
                generated_at=row[11],
                evaluation_date=row[12]
            ))
            
    except Exception as e:
        logger.warning(f"Failed to query active alerts from database: {e}. Falling back to CSV.")
        
    # Fallback to local CSV export if DB query fails or table is empty
    if not alerts:
        csv_path = "data/exports/active_pest_alerts.csv"
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                df = df.head(pg_limit)
                for _, row in df.iterrows():
                    alerts.append(PestAlertItem(
                        species=row["species"],
                        locality=row["locality"],
                        province=row["province"],
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        biofix_date=row["biofix_date"],
                        accumulated_gdd=float(row["accumulated_gdd"]),
                        days_active=int(row["days_active"]),
                        biological_stage=row["biological_stage"],
                        recommendation=row["recommendation"],
                        threat_level=row["threat_level"]
                    ))
            except Exception as csv_err:
                logger.error(f"Failed to parse active alerts CSV fallback: {csv_err}")
                raise HTTPException(status_code=500, detail=f"Database query failed and CSV fallback failed: {csv_err}")
        else:
            raise HTTPException(status_code=500, detail="Database query failed and no cached CSV alert export was found.")

    return ActiveAlertsResponse(alerts_count=len(alerts), alerts=alerts)


# --- Location-Based Geospatial Active Alerts Endpoint ---
@router.get("/api/v1/alerts/location", response_model=ActiveAlertsResponse, dependencies=[Depends(verify_api_key)])
def active_alerts_by_location(
    lat: float, 
    lng: float, 
    radius_km: Optional[float] = None, 
    db: Session = Depends(get_db),
    limit: Optional[int] = None
):
    """
    Retrieves active thermodynamic pest alerts within a given radius of a location (Lat/Lng).
    """
    target_radius = radius_km or settings.default_geospatial_radius_km
    radius_meters = target_radius * 1000.0
    pg_limit = limit or settings.default_pagination_limit
    
    alerts = []
    
    try:
        # Use PostGIS on-the-fly calculations for numeric lat/lng columns in pest_alerts
        query = text(
            "SELECT species, locality, province, latitude, longitude, biofix_date, "
            "accumulated_gdd, days_active, biological_stage, recommendation, threat_level, "
            "generated_at, evaluation_date, "
            "ST_Distance("
            "    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography, "
            "    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"
            ") / 1000.0 as distance_km "
            "FROM pest_alerts "
            "WHERE ST_DWithin("
            "    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography, "
            "    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, "
            "    :radius_meters"
            ") "
            "ORDER BY distance_km ASC "
            "LIMIT :limit"
        )
        res = db.execute(query, {
            "lng": lng, 
            "lat": lat, 
            "radius_meters": radius_meters,
            "limit": pg_limit
        }).fetchall()
        
        for row in res:
            alerts.append(PestAlertItem(
                species=row[0],
                locality=row[1],
                province=row[2],
                latitude=float(row[3]),
                longitude=float(row[4]),
                biofix_date=row[5],
                accumulated_gdd=float(row[6]),
                days_active=int(row[7]),
                biological_stage=row[8],
                recommendation=row[9],
                threat_level=row[10],
                generated_at=row[11],
                evaluation_date=row[12],
                distance_km=float(row[13]) if row[13] is not None else None
            ))
            
    except Exception as e:
        logger.warning(f"Failed to query database for location-based alerts: {e}. Falling back to CSV.")
        
    # Fallback to local CSV processing with Haversine formula calculation if DB fails
    if not alerts:
        csv_path = "data/exports/active_pest_alerts.csv"
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                candidates = []
                for _, row in df.iterrows():
                    row_lat = float(row["latitude"])
                    row_lng = float(row["longitude"])
                    dist = calculate_haversine(lat, lng, row_lat, row_lng)
                    
                    if dist <= target_radius:
                        candidates.append((dist, row))
                
                # Sort by distance and limit results
                candidates.sort(key=lambda x: x[0])
                for dist, row in candidates[:pg_limit]:
                    alerts.append(PestAlertItem(
                        species=row["species"],
                        locality=row["locality"],
                        province=row["province"],
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        biofix_date=row["biofix_date"],
                        accumulated_gdd=float(row["accumulated_gdd"]),
                        days_active=int(row["days_active"]),
                        biological_stage=row["biological_stage"],
                        recommendation=row["recommendation"],
                        threat_level=row["threat_level"],
                        distance_km=dist
                    ))
            except Exception as csv_err:
                logger.error(f"Failed to process active alerts CSV location fallback: {csv_err}")
                raise HTTPException(status_code=500, detail=f"Database query failed and CSV location fallback failed: {csv_err}")
        else:
            raise HTTPException(status_code=500, detail="Database query failed and no cached CSV alert export was found.")
            
    return ActiveAlertsResponse(alerts_count=len(alerts), alerts=alerts)


# --- Risk Zones Endpoints ---
@router.get("/api/v1/predictions/risk-zones", response_model=PredictionsResponse, dependencies=[Depends(verify_api_key)])
def risk_zones(limit: Optional[int] = None):
    """
    Retrieves XGBoost Warning Level 1 predictions representing pest outbreak vulnerability risk zones.
    """
    pg_limit = limit or settings.default_pagination_limit
    csv_path = "data/exports/pest_monitoring_dataset.csv"
    predictions = []
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            # Filter for severe predictions or simple head load to keep it fast
            predictions = df.head(pg_limit).to_dict(orient="records")
        except Exception as e:
            logger.error(f"Failed to read predictions dataset: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        logger.warning(f"Dataset not found at {csv_path}. Run ETL pipeline first.")
        
    return PredictionsResponse(predictions_count=len(predictions), predictions=predictions)
