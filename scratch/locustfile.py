from locust import HttpUser, task, between
import random

class PlagoutApiUser(HttpUser):
    # Simulate users taking a pause between 1 and 3 seconds between actions
    wait_time = between(1, 3)

    def on_start(self):
        """
        Called when a simulated user starts running.
        Sets up authorization headers.
        """
        # Default secret token used for Android app authentication
        self.headers = {
            "X-API-KEY": "plagout_secret_token_123",
            "Content-Type": "application/json"
        }
        
        # Define key agrarian regions in Argentina for coordinates simulation
        self.locations = [
            {"name": "Pergamino", "lat": -33.89, "lng": -60.57},
            {"name": "Tucuman", "lat": -26.82, "lng": -65.22},
            {"name": "Balcarce", "lat": -37.84, "lng": -58.26},
            {"name": "Cordoba", "lat": -31.41, "lng": -64.18},
            {"name": "Santa Fe", "lat": -31.63, "lng": -60.70},
        ]

    @task(3)
    def test_location_based_alerts(self):
        """
        Simulates the Android app requesting nearby pest alerts based on GPS location.
        This is our most expensive geospatial (PostGIS) query!
        """
        loc = random.choice(self.locations)
        # Add random jitter to simulate diverse field positions around key hubs
        lat_jitter = loc["lat"] + random.uniform(-0.1, 0.1)
        lng_jitter = loc["lng"] + random.uniform(-0.1, 0.1)
        # Select optional radius from 5km up to 50km
        radius = random.choice([5.0, 10.0, 20.0, 50.0])
        
        self.client.get(
            f"/api/v1/alerts/location?lat={lat_jitter}&lng={lng_jitter}&radius_km={radius}",
            headers=self.headers,
            name="/api/v1/alerts/location [Geospatial Search]"
        )

    @task(2)
    def test_active_alerts_list(self):
        """
        Simulates viewing a global/paginated dashboard feed of active alerts.
        """
        limit = random.choice([10, 20, 50])
        self.client.get(
            f"/api/v1/alerts/active?limit={limit}",
            headers=self.headers,
            name="/api/v1/alerts/active [Dashboard Feed]"
        )

    @task(2)
    def test_gdd_simulation(self):
        """
        Simulates the user triggering a daily GDD progression check.
        """
        loc = random.choice(self.locations)
        payload = {
            "latitude": loc["lat"],
            "longitude": loc["lng"],
            "currentDate": "2026-05-23",
            "initialGDD": random.randint(50, 300),
            "targetGDD": 380,
            "baseTemperature": 10.0
        }
        self.client.post(
            "/api/v1/gdd/simulate-day",
            json=payload,
            headers=self.headers,
            name="/api/v1/gdd/simulate-day [GDD Sim]"
        )

    @task(1)
    def test_api_health(self):
        """
        Basic service check that triggers database connection checks.
        """
        self.client.get("/api/v1/health", name="/api/v1/health [Health Check]")
