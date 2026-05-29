import os
import logging
from typing import Dict, List, Any
import pandas as pd
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Plag-out Delivery API",
    description="Secure REST API for accessing active thermodynamic pest alerts and risk zone predictions.",
    version="1.0.0"
)

# API Key Authentication Setup
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key(api_key: str = Depends(api_key_header)):
    expected_key = os.environ.get("PLAGOUT_API_KEY", "plagout_secret_token_123")
    if api_key != expected_key:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, 
            detail="Could not validate credentials: Invalid X-API-KEY header."
        )
    return api_key

@app.get("/api/v1/health")
def health_check():
    """
    Service health check endpoint.
    """
    return {"status": "healthy", "database": "connected"}

@app.get("/api/v1/alerts/active", dependencies=[Depends(verify_api_key)])
def active_alerts():
    """
    Retrieves active thermodynamic pest alerts from the database.
    """
    from loaders.db import get_engine
    from sqlalchemy import text
    
    engine = get_engine()
    alerts = []
    try:
        with engine.connect() as conn:
            query = text(
                "SELECT id, occurrence_date, pest_type, severity_level, ST_AsText(geom::geometry) as coords "
                "FROM pest_monitoring "
                "WHERE severity_level IN ('Explosive', 'High', 'Official Alert (Confirmed: Presente)', 'Official Alert (Confirmed: Presente ampliamente distribuida)') "
                "ORDER BY occurrence_date DESC LIMIT 100"
            )
            res = conn.execute(query)
            for row in res:
                alerts.append({
                    "id": row[0],
                    "date": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
                    "pest_type": row[2],
                    "severity_level": row[3],
                    "coordinates": row[4]
                })
    except Exception as e:
        logger.error(f"Failed to query active alerts: {e}")
        # Fallback to local exports if DB query fails during migration phase
        csv_path = "data/exports/active_pest_alerts.csv"
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            alerts = df.head(100).to_dict(orient="records")
        else:
            raise HTTPException(status_code=500, detail=f"Database query failed and no cached CSV alert export was found: {e}")
            
    return {"alerts_count": len(alerts), "alerts": alerts}

@app.get("/api/v1/predictions/risk-zones", dependencies=[Depends(verify_api_key)])
def risk_zones():
    """
    Retrieves XGBoost Warning Level 1 predictions representing pest outbreak vulnerability risk zones.
    """
    csv_path = "data/exports/pest_monitoring_dataset.csv"
    predictions = []
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            predictions = df.head(100).to_dict(orient="records")
        except Exception as e:
            logger.error(f"Failed to read predictions dataset: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        logger.warning(f"Dataset not found at {csv_path}. Run ETL pipeline first.")
        
    return {"predictions_count": len(predictions), "predictions": predictions}
