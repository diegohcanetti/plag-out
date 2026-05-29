from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Re-export GDD schemas from gdd_service to maintain compatibility and modularity
from gdd_service import GDDSimulationRequest, GDDSimulationResponse

class HealthResponse(BaseModel):
    status: str
    database: str

class GDDHealthResponse(BaseModel):
    status: str

class PestAlertItem(BaseModel):
    id: Optional[int] = None
    species: str
    locality: str
    province: str
    latitude: float
    longitude: float
    biofix_date: str
    accumulated_gdd: float
    days_active: int
    biological_stage: str
    recommendation: str
    threat_level: str
    generated_at: Optional[datetime] = None
    evaluation_date: Optional[datetime] = None
    distance_km: Optional[float] = None

class ActiveAlertsResponse(BaseModel):
    alerts_count: int
    alerts: List[PestAlertItem]

class PredictionsResponse(BaseModel):
    predictions_count: int
    predictions: List[Dict[str, Any]]
