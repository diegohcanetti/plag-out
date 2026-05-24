"""
Plag-out Machine Learning & Biological Pipeline Master Runner

This script executes the complete predictive and thermodynamic workflow for Plag-out:
1. Retrospectively extracts empirical Biofixes from trap data (Step 1).
2. Features engineering & Warning Level 1 predictive XGBoost training (Steps 2-3).
3. Warning Level 2 Thermodynamic tracking for active overlapping cohorts (Step 4).
4. Executes the Fallback Protocol comparing Spodoptera frugiperda vs. Dalbulus maidis (Step 5).
5. Generates high-fidelity visual assets, reports, and saves predictions to CSV.
"""

import os
import argparse
import logging
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Pipeline imports
from ml.biofix import BiofixExtractor, BiofixCohort
from ml.climate import ClimateProvider, GDDCalculator, PEST_BIOLOGY
from ml.predictors import FeatureEngineer, WarningLevel1Model
from ml.engine import ThermodynamicEngine
from loaders.db import get_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ml_pipeline")


def run_full_ml_pipeline(test_mode: bool = False):
    logger.info("======================================================================")
    logger.info("        STARTING PLAG-OUT ML & THERMODYNAMIC PREDICTIVE PIPELINE       ")
    logger.info("======================================================================")
    
    # Connect directly to the database and retrieve occurrences
    try:
        db_engine = get_engine()
        query = (
            "SELECT id, occurrence_date, pest_type, severity_level, institution, "
            "province, locality, adults_count, infection_percent, ST_AsText(geom) as geom_wkt "
            "FROM pest_monitoring"
        )
        pest_df = pd.read_sql_query(query, con=db_engine)
        logger.info(f"Loaded {len(pest_df)} historical pest occurrence records directly from database.")
    except Exception as e:
        logger.error(f"Failed to fetch data directly from PostgreSQL: {e}")
        raise
    
    # Initialize Climate Provider and GDD Calculator
    # In test_mode or offline, we use synthetic climate telemetry. Otherwise, we fetch NASA POWER.
    # To keep it extremely robust and fast, we use the cached NASA POWER API client
    cp = ClimateProvider(use_api=True) 
    fe = FeatureEngineer(cp)
    engine = ThermodynamicEngine(cp)
    
    # --------------------------------------------------------------------------
    # STEP 1 & 5: RETROSPECTIVE BIOFIX & FALLBACK SPECIES COMPARISON
    # --------------------------------------------------------------------------
    logger.info("\n--- STEP 1: Programmatically Extracting Empirical Biofixes ---")
    bio_extractor = BiofixExtractor(min_adults_threshold=10.0, separation_days=28)
    all_cohorts = bio_extractor.extract_biofixes(pest_df)
    
    # Separate cohorts by pest species (Fallback Protocol)
    dm_cohorts = [c for c in all_cohorts if c.species == "Dalbulus maidis"]
    sf_cohorts = [c for c in all_cohorts if c.species == "Spodoptera frugiperda"]
    
    logger.info(f"Dalbulus maidis: programmatically extracted {len(dm_cohorts)} cohort threads.")
    logger.info(f"Spodoptera frugiperda (Secondary Pest): extracted {len(sf_cohorts)} cohort threads.")
    
    # --------------------------------------------------------------------------
    # STEPS 2 & 3: FEATURE ENGINEERING & WARNING LEVEL 1 XGBOOST MODELS
    # --------------------------------------------------------------------------
    logger.info("\n--- STEPS 2 & 3: Warning Level 1 Predictive XGBoost Training ---")
    wl1_dm = WarningLevel1Model(model_dir="data/models/dalbulus_maidis")
    wl1_sf = WarningLevel1Model(model_dir="data/models/spodoptera_frugiperda")
    
    # We trim training sets if in test_mode to keep execution quick
    df_dm_train = pest_df if not test_mode else pest_df.head(150)
    df_sf_train = pest_df if not test_mode else pest_df.head(150)
    
    # Dalbulus maidis Model
    logger.info("Training Model for primary pest (Dalbulus maidis)...")
    X_dm, y_dm = wl1_dm.prepare_dataset(df_dm_train, fe, "Dalbulus maidis")
    metrics_dm = wl1_dm.train(X_dm, y_dm)
    
    # Spodoptera frugiperda Model
    logger.info("Training Model for secondary pest (Spodoptera frugiperda)...")
    X_sf, y_sf = wl1_sf.prepare_dataset(df_sf_train, fe, "Spodoptera frugiperda")
    metrics_sf = wl1_sf.train(X_sf, y_sf)
    
    # --------------------------------------------------------------------------
    # STEP 4: WARNING LEVEL 2 THERMODYNAMIC LIFECYCLE TRACKING
    # --------------------------------------------------------------------------
    logger.info("\n--- STEP 4: Warning Level 2 Biological Thermodynamic Tracking ---")
    
    # Track the active state of all cohorts as of "today" (May 23, 2026)
    evaluation_date = datetime(2026, 5, 23)
    logger.info(f"Evaluating active cohort biological stages and GDD windows as of {evaluation_date.strftime('%Y-%m-%d')}...")
    
    active_alerts = []
    
    # Track first 20 active Dalbulus maidis cohorts
    logger.info("Tracking active Dalbulus maidis thermodynamic cohorts...")
    for cohort in dm_cohorts[:20]:
        report = engine.track_cohort(cohort, evaluation_date)
        if report["status"] == "Active":
            active_alerts.append({
                "species": cohort.species,
                "locality": cohort.locality,
                "province": cohort.province,
                "latitude": cohort.latitude,
                "longitude": cohort.longitude,
                "biofix_date": cohort.biofix_date.strftime('%Y-%m-%d'),
                "accumulated_gdd": report["accumulated_gdd"],
                "days_active": report["days_active"],
                "biological_stage": report["current_stage"],
                "recommendation": report["recommendation"],
                "threat_level": report["threat_level"]
            })
            
    # Track all active Spodoptera frugiperda cohorts
    logger.info("Tracking active Spodoptera frugiperda thermodynamic cohorts...")
    for cohort in sf_cohorts:
        report = engine.track_cohort(cohort, evaluation_date)
        if report["status"] == "Active":
            active_alerts.append({
                "species": cohort.species,
                "locality": cohort.locality,
                "province": cohort.province,
                "latitude": cohort.latitude,
                "longitude": cohort.longitude,
                "biofix_date": cohort.biofix_date.strftime('%Y-%m-%d'),
                "accumulated_gdd": report["accumulated_gdd"],
                "days_active": report["days_active"],
                "biological_stage": report["current_stage"],
                "recommendation": report["recommendation"],
                "threat_level": report["threat_level"]
            })
            
    alerts_df = pd.DataFrame(active_alerts)
    
    # Ensure exports directory exists and write CSV for backup
    alerts_csv = "data/exports/active_pest_alerts.csv"
    os.makedirs(os.path.dirname(alerts_csv), exist_ok=True)
    alerts_df.to_csv(alerts_csv, index=False)
    logger.info(f"Successfully generated active thermodynamic alerts and exported to {alerts_csv}")
    
    # Persist the active alerts back to PostgreSQL database for event sourcing
    if not alerts_df.empty:
        try:
            alerts_df_to_save = alerts_df.copy()
            alerts_df_to_save["generated_at"] = datetime.now(timezone.utc)
            alerts_df_to_save["evaluation_date"] = evaluation_date
            
            alerts_df_to_save.to_sql("pest_alerts", con=db_engine, if_exists="append", index=False)
            logger.info("Successfully persisted active thermodynamic alerts to 'pest_alerts' table in PostgreSQL.")
        except Exception as e:
            logger.error(f"Failed to persist active alerts to PostgreSQL: {e}")
    else:
        logger.warning("No active thermodynamic alerts generated to persist to PostgreSQL.")
    
    # --------------------------------------------------------------------------
    # REPORTING & VISUALIZATION (WOW FACTOR)
    # --------------------------------------------------------------------------
    logger.info("\n--- STEP 5 & 6: Generating High-Fidelity Validation Assets ---")
    
    # Let's print out the summary table beautifully
    print("\n" + "="*80)
    print("                 PLAG-OUT ACTIVE THERMODYNAMIC ALERTS SUMMARY")
    print("="*80)
    print(alerts_df[['species', 'province', 'locality', 'accumulated_gdd', 'biological_stage', 'threat_level']].head(15).to_string(index=False))
    print("="*80)
    
    # Generate GDD Accumulation Curves plot for key regions
    plt.figure(figsize=(10, 6))
    
    # Choose 3 representative cohorts
    rep_cohorts = []
    if dm_cohorts:
        rep_cohorts.append(dm_cohorts[0])
    if sf_cohorts:
        rep_cohorts.append(sf_cohorts[0])
    if len(dm_cohorts) > 1:
        rep_cohorts.append(dm_cohorts[1])
        
    for cohort in rep_cohorts:
        weather_df = cp.get_weather(cohort.latitude, cohort.longitude, cohort.biofix_date, evaluation_date)
        tbase = PEST_BIOLOGY[cohort.species]["tbase"]
        tupper = PEST_BIOLOGY[cohort.species]["tupper"]
        
        # Recalculate daily/cum GDD
        weather_df['daily_gdd'] = weather_df.apply(
            lambda r: GDDCalculator.calculate_daily_gdd(r['temp_max'], r['temp_min'], tbase, tupper), axis=1
        )
        weather_df['cumulative_gdd'] = weather_df['daily_gdd'].cumsum()
        
        plt.plot(weather_df['date'], weather_df['cumulative_gdd'], label=f"{cohort.species} at {cohort.locality} (Biofix: {cohort.biofix_date.strftime('%Y-%m-%d')})", linewidth=2)
        
    dm_gdd = PEST_BIOLOGY.get("Dalbulus maidis", {}).get("generation_gdd", 381.0)
    sf_gdd = PEST_BIOLOGY.get("Spodoptera frugiperda", {}).get("generation_gdd", 378.0)
    
    plt.axhline(y=dm_gdd, color='r', linestyle='--', alpha=0.7, label=f"Dalbulus Generation GDD Threshold ({int(dm_gdd)})")
    plt.axhline(y=sf_gdd, color='g', linestyle=':', alpha=0.7, label=f"Spodoptera Generation GDD Threshold ({int(sf_gdd)})")
    
    plt.title("Growing Degree Days (GDD) Accumulation from Empirical Biofix Dates", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Cumulative Growing Degree Days", fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc="upper left")
    plt.tight_layout()
    
    plot_path = "data/exports/gdd_accumulation_curves.png"
    plt.savefig(plot_path, dpi=300)
    logger.info(f"Saved visual thermodynamic curve comparison to {plot_path}")
    
    print("\n" + "="*80)
    print("                    PIPELINE MODEL ACCURACY COMPARISON REPORT")
    print("="*80)
    print(f"Primary Pest (Dalbulus maidis) XGBoost Accuracy: {metrics_dm['accuracy']*100:.2f}% | AUC-ROC: {metrics_dm['auc']:.4f}")
    print(f"Secondary Pest (Spodoptera frugiperda) XGBoost Accuracy: {metrics_sf['accuracy']*100:.2f}% | AUC-ROC: {metrics_sf['auc']:.4f}")
    print("="*80)
    
    logger.info("Plag-out ML & Thermodynamic pipeline execution fully complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plag-out ML Pipeline")
    parser.add_argument("--test", action="store_true", help="Runs pipeline in high-speed test mode with small sample size")
    args = parser.parse_args()
    
    run_full_ml_pipeline(test_mode=args.test)
