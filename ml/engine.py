"""
Plag-out Machine Learning Pipeline: Warning Level 2 (Deterministic Thermodynamic Engine)

This module implements the Warning Level 2 biological tracker.
It accumulates Growing Degree Days (GDD) starting from empirical Biofix dates,
maps GDD to specific pest lifecycle stages (eggs, nymphs/larvae, pupae, adults),
and issues precise, multi-cohort operational treatment window alerts.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np

from ml.climate import ClimateProvider, GDDCalculator, PEST_BIOLOGY
from ml.biofix import BiofixCohort

logger = logging.getLogger(__name__)


class BiologicalStage:
    """
    Utility representing a specific biological lifecycle stage and its associated
    vulnerability, treatment action, and GDD range.
    """
    def __init__(self, name: str, gdd_start: float, gdd_end: float, action: str, threat_level: str):
        self.name = name
        self.gdd_start = gdd_start
        self.gdd_end = gdd_end
        self.action = action
        self.threat_level = threat_level  # Low, Info, Warning, Critical

    def contains(self, cumulative_gdd: float) -> bool:
        return self.gdd_start <= cumulative_gdd < self.gdd_end

    def __repr__(self) -> str:
        return f"Stage({self.name}, GDD: {self.gdd_start}-{self.gdd_end}, Threat: {self.threat_level})"


class ThermodynamicEngine:
    """
    Warning Level 2 biological tracker which manages multiple concurrent cohort threads,
    projects GDD accumulation, and issues treatment windows.
    """
    def __init__(self, climate_provider: ClimateProvider):
        self.climate_provider = climate_provider
        self.gdd_calc = GDDCalculator()

    def get_lifecycle_stages(self, species: str) -> List[BiologicalStage]:
        """
        Retrieves the standard biological GDD breakpoints for a species.
        """
        bio = PEST_BIOLOGY.get(species)
        if not bio:
            raise ValueError(f"Unknown species biology: {species}")
            
        stages = []
        if "nymph_gdd" in bio:
            stages = [
                BiologicalStage("Egg Development", 0.0, bio["egg_gdd"], 
                                "Monitor egg parasitoids (biocontrol). Treatment generally not required.", "Low"),
                BiologicalStage("Nymph Emergence & Feeding (Critical)", bio["egg_gdd"], bio["egg_gdd"] + bio["nymph_gdd"], 
                                "CRITICAL WINDOW: Apply precision insecticides or biologicals (Beauveria bassiana). High feeding threat.", "Critical"),
                BiologicalStage("Pre-Oviposition Adults", bio["egg_gdd"] + bio["nymph_gdd"], bio["generation_gdd"], 
                                "WARNING WINDOW: Prevent adult mating and egg-laying. Apply systemic controls.", "Warning"),
                BiologicalStage("Subsequent Generation Emergence", bio["generation_gdd"], float('inf'), 
                                "ALERT: Next generation cohort starting. Trap monitoring highly recommended.", "Warning")
            ]
        else:
            egg = bio.get("egg_gdd", 40.0)
            larva = bio.get("larva_gdd", 200.0)
            pupa = bio.get("pupa_gdd", 120.0)
            preovip = bio.get("preoviposition_gdd", 35.0)
            gen = bio.get("generation_gdd", egg + larva + pupa + preovip)
            
            stages = [
                BiologicalStage("Egg Development", 0.0, egg, 
                                "Apply egg-parasitic biocontrols (Trichogramma). Check lower leaf faces.", "Low"),
                BiologicalStage("Larval Growth & Devastating Feeding", egg, egg + larva, 
                                "CRITICAL WINDOW: Apply Bt-toxins, physiological insecticides, or Baculovirus. Extremely high defoliation risk.", "Critical"),
                BiologicalStage("Pupal Phase (Soil)", egg + larva, egg + larva + pupa, 
                                "INFO: Cohort pupating in soil. Prepare traps for adult emergence.", "Info"),
                BiologicalStage("Moths & Oviposition", egg + larva + pupa, gen, 
                                "WARNING WINDOW: Moths actively laying eggs. Apply light/pheromone traps and foliar deterrents.", "Warning"),
                BiologicalStage("Subsequent Generation Emergence", gen, float('inf'), 
                                "ALERT: Second generation larval wave beginning. Re-evaluate monitoring protocols.", "Warning")
            ]
            
        return stages

    def track_cohort(
        self,
        cohort: BiofixCohort,
        evaluation_date: datetime
    ) -> Dict[str, any]:
        """
        Accumulates thermodynamic GDD from the cohort's empirical Biofix to the evaluation_date,
        determines the current active biological stage, and outputs action recommendations.
        """
        species = cohort.species
        bio = PEST_BIOLOGY.get(species)
        if not bio:
            raise ValueError(f"No biology constants defined for: {species}")
            
        # If the evaluation date is before the Biofix, the cohort hasn't started yet
        biofix_dt = cohort.biofix_date.replace(tzinfo=None)
        eval_dt = evaluation_date.replace(tzinfo=None)
        
        if eval_dt < biofix_dt:
            return {
                "cohort": cohort,
                "status": "Not Started",
                "accumulated_gdd": 0.0,
                "days_active": 0,
                "current_stage": None,
                "recommendation": "Cohort has not yet been initiated.",
                "threat_level": "None"
            }
            
        # Retrieve climate telemetry from Biofix to evaluation date
        weather_df = self.climate_provider.get_weather(
            cohort.latitude, cohort.longitude, biofix_dt, eval_dt
        )
        
        # Accumulate GDD
        accum_df = self.gdd_calc.accumulate_gdd(weather_df, tbase=bio["tbase"], tupper=bio.get("tupper"))
        
        total_gdd = float(accum_df['cumulative_gdd'].iloc[-1]) if len(accum_df) > 0 else 0.0
        days_active = len(accum_df)
        
        # Determine biological stage
        stages = self.get_lifecycle_stages(species)
        current_stage = None
        for stage in stages:
            if stage.contains(total_gdd):
                current_stage = stage
                break
                
        # In case GDD exceeds the largest stage's end, default to subsequent generation
        if current_stage is None and len(stages) > 0:
            current_stage = stages[-1]
            
        return {
            "cohort": cohort,
            "status": "Active",
            "accumulated_gdd": total_gdd,
            "days_active": days_active,
            "current_stage": current_stage.name if current_stage else "Unknown",
            "recommendation": current_stage.action if current_stage else "N/A",
            "threat_level": current_stage.threat_level if current_stage else "Low"
        }

    def aggregate_location_alerts(
        self,
        cohorts: List[BiofixCohort],
        evaluation_date: datetime
    ) -> Dict[str, List[Dict[str, any]]]:
        """
        Consolidates alerts across multiple active, concurrent cohort threads (overlapping generations)
        at different locations.
        """
        location_reports: Dict[str, List[Dict[str, any]]] = {}
        
        for cohort in cohorts:
            loc_key = f"{cohort.province} - {cohort.locality} ({cohort.latitude:.4f}, {cohort.longitude:.4f})"
            report = self.track_cohort(cohort, evaluation_date)
            
            if loc_key not in location_reports:
                location_reports[loc_key] = []
                
            location_reports[loc_key].append(report)
            
        return location_reports


if __name__ == "__main__":
    # Test thermodynamic engine
    logging.basicConfig(level=logging.INFO)
    
    cp = ClimateProvider(use_api=False)  # offline synthetic
    engine = ThermodynamicEngine(cp)
    
    # Define a test cohort
    cohort = BiofixCohort(
        species="Dalbulus maidis",
        biofix_date=datetime(2026, 1, 1),
        peak_count=120.0,
        locality="EL Carmen",
        province="Jujuy",
        coord=(-24.3833, -65.25)
    )
    
    # Track cohort progress 12 days later
    eval_date = datetime(2026, 1, 12)
    report = engine.track_cohort(cohort, eval_date)
    print("Thermodynamic Tracker Report 12 days post-Biofix:")
    print(" - Species:", report["cohort"].species)
    print(" - Accumulated GDD:", report["accumulated_gdd"])
    print(" - Current Stage:", report["current_stage"])
    print(" - Recommendation:", report["recommendation"])
    print(" - Threat Level:", report["threat_level"])
