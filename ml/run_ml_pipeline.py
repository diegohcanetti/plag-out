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
import gc
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
    
    # Group cohorts by pest species dynamically
    cohorts_by_species = {}
    for c in all_cohorts:
        cohorts_by_species.setdefault(c.species, []).append(c)
        
    for species, cohorts in cohorts_by_species.items():
        logger.info(f"{species}: programmatically extracted {len(cohorts)} cohort threads.")
    
    # --------------------------------------------------------------------------
    # STEPS 2 & 3: FEATURE ENGINEERING & WARNING LEVEL 1 XGBOOST MODELS
    # --------------------------------------------------------------------------
    logger.info("\n--- STEPS 2 & 3: Warning Level 1 Predictive XGBoost Training ---")
    
    metrics_report = {}
    
    # Dynamically train model for each configured pest species
    for pest_name in PEST_BIOLOGY.keys():
        # Trim training sets if in test_mode to keep execution quick
        df_train = pest_df if not test_mode else pest_df.head(150)
        
        # Filter for records of this pest type to check if there is data
        df_pest_only = df_train[df_train['pest_type'] == pest_name]
        if df_pest_only.empty:
            logger.info(f"No records found for {pest_name} in dataset. Skipping model training.")
            continue
            
        logger.info(f"Training Model for pest species: {pest_name}...")
        pest_slug = pest_name.lower().replace(" ", "_")
        wl1 = WarningLevel1Model(model_dir=f"data/models/{pest_slug}")
        
        try:
            X, y = wl1.prepare_dataset(df_train, fe, pest_name)
            if len(X) < 5:
                logger.warning(f"Insufficient samples ({len(X)}) to train model for {pest_name}. Skipping.")
                continue
                
            metrics = wl1.train(X, y)
            metrics_report[pest_name] = metrics
            
            # Performance quality gate check:
            acc = metrics.get("accuracy", 0.0)
            f1 = metrics.get("f1_score", 0.0)
            threshold = 0.75
            
            logger.info(f"Model performance validation gate: Accuracy = {acc:.4f}, F1-Score = {f1:.4f} (threshold: {threshold})")
            if acc < threshold or f1 < threshold:
                if not test_mode:
                    raise RuntimeError(
                        f"Model performance degraded below threshold ({threshold}) for {pest_name}! "
                        f"Accuracy: {acc:.4f}, F1-Score: {f1:.4f}. Aborting pipeline to prevent poisoning predictions."
                    )
                else:
                    logger.warning(
                        f"⚠️ Model performance ({acc:.4f} Accuracy, {f1:.4f} F1) is below {threshold}, "
                        f"but proceeding because test_mode=True."
                    )
        except Exception as e:
            logger.error(f"Failed to train or validate Warning Level 1 model for {pest_name}: {e}")
            raise
        finally:
            # Free up XGBoost model memory to prevent OOM
            if 'wl1' in locals():
                del wl1
            if 'X' in locals():
                del X
            if 'y' in locals():
                del y
            gc.collect()
            
    # --------------------------------------------------------------------------
    # STEP 4: WARNING LEVEL 2 THERMODYNAMIC LIFECYCLE TRACKING
    # --------------------------------------------------------------------------
    logger.info("\n--- STEP 4: Warning Level 2 Biological Thermodynamic Tracking ---")
    
    # Track the active state of all cohorts dynamically as of "today"
    evaluation_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    logger.info(f"Evaluating active cohort biological stages and GDD windows as of {evaluation_date.strftime('%Y-%m-%d')}...")
    
    active_alerts = []
    
    # Track active cohorts dynamically across all species
    for species, cohorts in cohorts_by_species.items():
        logger.info(f"Tracking active {species} thermodynamic cohorts...")
        # Process up to 20 active cohorts per species to keep things balanced
        for cohort in cohorts[:20]:
            try:
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
            except Exception as e:
                logger.error(f"Error tracking cohort for species {species}: {e}")
            
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
    if not alerts_df.empty:
        print(alerts_df[['species', 'province', 'locality', 'accumulated_gdd', 'biological_stage', 'threat_level']].head(15).to_string(index=False))
    else:
        print("No active alerts generated.")
    print("="*80)
    
    # Generate GDD Accumulation Curves plot for key regions
    plt.figure(figsize=(10, 6))
    
    # Choose representative cohorts dynamically across different species
    rep_cohorts = []
    seen_species = set()
    for cohort in all_cohorts:
        if cohort.species not in seen_species:
            rep_cohorts.append(cohort)
            seen_species.add(cohort.species)
        if len(rep_cohorts) >= 4:
            break
            
    # Draw GDD accumulation curves
    for cohort in rep_cohorts:
        try:
            # Ensure both dates are tz-naive for consistent Pandas processing and API calls
            b_date = cohort.biofix_date.replace(tzinfo=None) if cohort.biofix_date.tzinfo else cohort.biofix_date
            e_date = evaluation_date.replace(tzinfo=None) if evaluation_date.tzinfo else evaluation_date
            
            # Ensure start date is strictly before or equal to end date to prevent NASA POWER 422 errors
            start_dt = min(b_date, e_date)
            end_dt = max(b_date, e_date)
            
            weather_df = cp.get_weather(cohort.latitude, cohort.longitude, start_dt, end_dt)
            tbase = PEST_BIOLOGY[cohort.species]["tbase"]
            tupper = PEST_BIOLOGY[cohort.species]["tupper"]
            
            # Recalculate daily/cum GDD
            weather_df['daily_gdd'] = weather_df.apply(
                lambda r: GDDCalculator.calculate_daily_gdd(r['temp_max'], r['temp_min'], tbase, tupper), axis=1
            )
            weather_df['cumulative_gdd'] = weather_df['daily_gdd'].cumsum()
            
            plt.plot(weather_df['date'], weather_df['cumulative_gdd'], 
                     label=f"{cohort.species} at {cohort.locality} (Biofix: {cohort.biofix_date.strftime('%Y-%m-%d')})", linewidth=2)
        except Exception as e:
            logger.error(f"Failed to plot curve for cohort {cohort}: {e}")
            
    # Draw generation thresholds dynamically
    colors = ['r', 'g', 'b', 'c', 'm', 'y']
    linestyles = ['--', ':', '-.', '--', ':', '-.']
    for idx, cohort in enumerate(rep_cohorts):
        gen_gdd = PEST_BIOLOGY.get(cohort.species, {}).get("generation_gdd", 380.0)
        color = colors[idx % len(colors)]
        style = linestyles[idx % len(linestyles)]
        plt.axhline(y=gen_gdd, color=color, linestyle=style, alpha=0.6, 
                    label=f"{cohort.species} Gen GDD Threshold ({int(gen_gdd)})")
    
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
    for pest_name, metrics in metrics_report.items():
        print(f"{pest_name} XGBoost Accuracy: {metrics['accuracy']*100:.2f}% | AUC-ROC: {metrics['auc']:.4f}")
    print("="*80)
    
    logger.info("Plag-out ML & Thermodynamic pipeline execution fully complete!")
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plag-out ML Pipeline")
    parser.add_argument("--test", action="store_true", help="Runs pipeline in high-speed test mode with small sample size")
    args = parser.parse_args()
    
    run_full_ml_pipeline(test_mode=args.test)
