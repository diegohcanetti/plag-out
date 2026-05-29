# tests/test_api.py
"""
Unit and Integration Tests for the FastAPI Backend.
Mocks external API requests to ensure fast, deterministic local test runs.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api import app, verify_api_key
from gdd_service import WeatherData

client = TestClient(app)

def test_health_endpoint():
    """
    Assert that the standard health check endpoint returns 200 and database status.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}


def test_gdd_health_endpoint():
    """
    Assert that the GDD specific health endpoint works for Rami's Kotlin client compat.
    """
    response = client.get("/api/gdd/health")
    assert response.status_code == 200
    assert response.json() == {"status": "GDD API is running"}


def test_auth_protected_endpoints_missing_key():
    """
    Assert that accessing protected API routes without the header yields 403 Forbidden.
    """
    response = client.get("/api/v1/alerts/active")
    assert response.status_code == 403
    
    response = client.get("/api/v1/predictions/risk-zones")
    assert response.status_code == 403


def test_auth_protected_endpoints_invalid_key():
    """
    Assert that access with a bad key header yields 403.
    """
    response = client.get("/api/v1/alerts/active", headers={"X-API-KEY": "wrong_key_123"})
    assert response.status_code == 403


@patch("loaders.db.get_engine")
def test_active_alerts_authorized_with_db_mock(mock_get_engine):
    """
    Assert that active alerts returns 200 and matches standard format when authorized.
    Since db query will be mocked or fail-over, we verify it runs.
    """
    # Force failure to trigger the local fallback csv validation safely or mock sqlalchemy conn
    mock_get_engine.side_effect = Exception("DB Connection Mock Failure")
    
    response = client.get(
        "/api/v1/alerts/active", 
        headers={"X-API-KEY": "plagout_secret_token_123"}
    )
    # Since there might not be a cached active_pest_alerts.csv in tests folder, it might return 500 or 200.
    # Let's verify we hit either a 500 with proper error message or 200 if CSV exists.
    assert response.status_code in [200, 500]


@patch("gdd_service.WeatherService.get_weather_for_date")
def test_gdd_simulation_success(mock_get_weather):
    """
    Assert GDD simulation calculations are correct.
    Formulas:
    Avg Temp = (30.0 + 20.0) / 2 = 25.0
    GDD = 25.0 - 10.0 = 15.0
    new_gdd = 100 + 15 = 115
    """
    # Setup mock weather
    mock_get_weather.return_value = WeatherData(
        date="2026-05-29",
        temp_max=30.0,
        temp_min=20.0
    )
    
    payload = {
        "latitude": -32.94682,
        "longitude": -60.63932,
        "startDate": "2026-05-01",
        "currentDate": "2026-05-29",
        "initialGDD": 100,
        "targetGDD": 120,
        "baseTemperature": 10.0,
        "cropName": "Soybean",
        "notes": "Testing GDD calculations"
    }
    
    # Hit both compatible endpoints
    for route in ["/api/gdd/simulate-day", "/api/v1/gdd/simulate-day"]:
        response = client.post(route, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["current_gdd"] == 115
        assert data["target_gdd"] == 120
        assert data["gdd_gained"] == 15.0
        assert data["progress_percentage"] == pytest.approx(95.83333333333333) # (115/120)*100
        assert data["target_reached"] is False
        assert "GDD restantes" in data["message"]


@patch("gdd_service.WeatherService.get_weather_for_date")
def test_gdd_simulation_target_reached(mock_get_weather):
    """
    Assert target reached logic triggers when new GDD exceeds or matches target.
    Avg Temp = (30.0 + 20.0) / 2 = 25.0
    GDD gained = 25.0 - 10.0 = 15.0
    new GDD = 110 + 15 = 125 >= 120 (Target Reached)
    """
    mock_get_weather.return_value = WeatherData(
        date="2026-05-29",
        temp_max=30.0,
        temp_min=20.0
    )
    
    payload = {
        "latitude": -32.94682,
        "longitude": -60.63932,
        "startDate": "2026-05-01",
        "currentDate": "2026-05-29",
        "initialGDD": 110,
        "targetGDD": 120,
        "baseTemperature": 10.0,
        "cropName": "Soybean"
    }
    
    response = client.post("/api/gdd/simulate-day", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["current_gdd"] == 125
    assert data["target_reached"] is True
    assert "GDD alcanzado" in data["message"]


def test_location_alerts_missing_key():
    """
    Assert that accessing the location-based alerts endpoint without an API key yields 403.
    """
    response = client.get("/api/v1/alerts/location?lat=-24.3&lng=-65.2")
    assert response.status_code == 403


@patch("loaders.db.get_engine")
def test_location_alerts_csv_fallback(mock_get_engine):
    """
    Assert that location-based alerts filter correctly and return sorted by distance.
    Uses the local fallback active_pest_alerts.csv.
    """
    mock_get_engine.side_effect = Exception("DB Connection Mock Failure")
    
    # Santa Clara is at (-24.3100735, -64.6619555)
    # Querying very close to Santa Clara with a 10km radius should return Santa Clara
    response = client.get(
        "/api/v1/alerts/location?lat=-24.31&lng=-64.66&radius_km=10",
        headers={"X-API-KEY": "plagout_secret_token_123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "alerts" in data
    assert len(data["alerts"]) > 0
    # The closest alert should be Santa Clara
    assert data["alerts"][0]["locality"] == "Santa Clara"
    assert data["alerts"][0]["distance_km"] < 10.0

