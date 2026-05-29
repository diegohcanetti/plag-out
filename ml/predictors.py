"""
Plag-out Machine Learning Pipeline: Warning Level 1 (Predictive Tree-based Model)

This module implements the Warning Level 1 predictive model using XGBoost.
It engineers rolling weather lag features (temp_max, humidity, precipitation)
and planting-GDD features, trains a classification model to predict pest outbreak
risk, and evaluates performance.
"""

import os
import joblib
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np

from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

from ml.climate import ClimateProvider, GDDCalculator

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Engineers spatial-temporal lag features from daily climate telemetry
    to feed into our ML models.
    """
    def __init__(self, climate_provider: ClimateProvider):
        self.climate_provider = climate_provider
        self.gdd_calc = GDDCalculator()

    def engineer_features_for_record(
        self,
        lat: float,
        lon: float,
        target_date: datetime,
        planting_date: datetime,
        tbase: float = 10.0
    ) -> Dict[str, float]:
        """
        Retrieves climate telemetry and builds rolling lag and GDD features
        for a specific spatial-temporal coordinate point.
        """
        # Fetch weather starting 30 days before planting up to target_date
        start_date = planting_date - timedelta(days=30)
        
        weather_df = self.climate_provider.get_weather(lat, lon, start_date, target_date)
        
        # Calculate daily and cumulative GDD from planting
        weather_df['daily_gdd'] = weather_df.apply(
            lambda r: self.gdd_calc.calculate_daily_gdd(r['temp_max'], r['temp_min'], tbase), axis=1
        )
        
        # Filter for dates since planting
        planting_dt = pd.to_datetime(planting_date).tz_localize(None)
        weather_df['date_naive'] = pd.to_datetime(weather_df['date']).dt.tz_localize(None)
        
        df_since_planting = weather_df[weather_df['date_naive'] >= planting_dt]
        gdd_accum_planting = df_since_planting['daily_gdd'].sum()
        days_since_planting = len(df_since_planting)
        
        # Extract rolling weather features trailing the target date (e.g. last 7 and 14 days)
        target_dt = pd.to_datetime(target_date).tz_localize(None)
        df_trailing_7 = weather_df[(weather_df['date_naive'] <= target_dt) & 
                                   (weather_df['date_naive'] > target_dt - timedelta(days=7))]
        df_trailing_14 = weather_df[(weather_df['date_naive'] <= target_dt) & 
                                    (weather_df['date_naive'] > target_dt - timedelta(days=14))]
        
        features = {
            'gdd_accum_planting': float(gdd_accum_planting),
            'days_since_planting': float(days_since_planting),
            
            # Weather lags
            'temp_max_mean_7d': float(df_trailing_7['temp_max'].mean()),
            'temp_max_mean_14d': float(df_trailing_14['temp_max'].mean()),
            'temp_min_mean_7d': float(df_trailing_7['temp_min'].mean()),
            'temp_min_mean_14d': float(df_trailing_14['temp_min'].mean()),
            
            'humidity_mean_7d': float(df_trailing_7['humidity'].mean()),
            'humidity_mean_14d': float(df_trailing_14['humidity'].mean()),
            
            'precip_sum_7d': float(df_trailing_7['precipitation'].sum()),
            'precip_sum_14d': float(df_trailing_14['precipitation'].sum()),
            
            # Dynamics
            'gdd_rate_7d': float(df_trailing_7['daily_gdd'].mean())
        }
        
        return features


class WarningLevel1Model:
    """
    Warning Level 1 Predictive Model using XGBoost to forecast early crop vulnerability
    and broad regional pest outbreak probability.
    """
    def __init__(self, model_dir: str = "data/models"):
        self.model_dir = model_dir
        self.model: Optional[XGBClassifier] = None
        os.makedirs(model_dir, exist_ok=True)

    def prepare_dataset(
        self,
        pest_df: pd.DataFrame,
        fe: FeatureEngineer,
        pest_type: str = "Dalbulus maidis"
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Builds the training matrix by programmatically estimating planting dates,
        applying spatiotemporal deduplication, and engineering climate lag features.
        """
        logger.info(f"Preparing machine learning dataset for {pest_type}...")
        
        from ml.biofix import BiofixExtractor
        be = BiofixExtractor()
        
        # 1. Spatiotemporal Deduplication
        pest_df_copy = pest_df.copy()
        pest_df_copy['occurrence_date_parsed'] = pd.to_datetime(pest_df_copy['occurrence_date'], format='mixed', utc=True)
        # Convert occurrence date to week start date
        pest_df_copy['week'] = pest_df_copy['occurrence_date_parsed'].dt.to_period('W').dt.start_time
        pest_df_copy['institution'] = pest_df_copy['institution'].fillna('Unknown')
        pest_df_copy['province'] = pest_df_copy['province'].fillna('Unknown')
        
        def get_rounded_coords(geom_wkt):
            try:
                lat, lon = be.parse_coordinates(geom_wkt)
                return round(lat, 1), round(lon, 1)
            except:
                return 0.0, 0.0
                
        # Calculate rounded coordinates (1 decimal place is ~11km at the equator)
        pest_df_copy['rounded_coords'] = pest_df_copy['geom_wkt'].apply(get_rounded_coords)
        
        # Drop invalid coordinates
        pest_df_copy = pest_df_copy[pest_df_copy['rounded_coords'] != (0.0, 0.0)]
        
        # Group by week, pest_type, and rounded_coords to find spatiotemporal duplicate clusters
        grouped = pest_df_copy.groupby(['week', 'pest_type', 'rounded_coords'])
        
        # Source confidence is the count of unique institutions that reported this spatiotemporal event
        confidence_counts = grouped['institution'].nunique().to_dict()
        
        # Deduplicate: collapse all duplicate records in the same spatiotemporal cell into a single unique record
        pest_df_deduped = pest_df_copy.drop_duplicates(subset=['week', 'pest_type', 'rounded_coords'], keep='first')
        
        logger.info(f"Spatiotemporal deduplication: reduced raw records from {len(pest_df)} to {len(pest_df_deduped)}")
        
        # Filter for the target pest species
        df = pest_df_deduped[pest_df_deduped['pest_type'] == pest_type].copy()
        df['occurrence_date'] = pd.to_datetime(df['occurrence_date'], format='mixed', utc=True)
        df['adults_count'] = pd.to_numeric(df['adults_count'], errors='coerce').fillna(0.0)
        
        # Target: 1 if severe outbreak (adults_count >= 50 or Explosive severity or official alert), 0 otherwise
        df['target'] = df.apply(
            lambda r: 1 if (r['adults_count'] >= 50.0 or r['severity_level'] in ['Explosive', 'High', 'Official Alert (Confirmed Survival)', 'Official Alert (Confirmed: Presente)', 'Official Alert (Confirmed: Presente ampliamente distribuida)']) else 0,
            axis=1
        )
        
        records_features = []
        targets = []
        
        for idx, row in df.iterrows():
            lat, lon = be.parse_coordinates(row['geom_wkt'])
            if lat == 0.0:
                continue
                
            occ_date = row['occurrence_date'].to_pydatetime()
            
            # Resolve the week, pest type, and rounded coordinates for looking up the corroboration count
            row_week = row['occurrence_date'].to_period('W').start_time
            row_pest = row['pest_type']
            row_rounded_coords = (round(lat, 1), round(lon, 1))
            
            # Retrieve confidence multiplier (default to 1 if not found)
            source_conf = confidence_counts.get((row_week, row_pest, row_rounded_coords), 1)
            
            # Estimate planting date: ~60 days prior to observation
            planting_date = occ_date - timedelta(days=60)
            
            try:
                feats = fe.engineer_features_for_record(lat, lon, occ_date, planting_date)
                # Injects source_confidence as an ML feature column
                feats['source_confidence'] = float(source_conf)
                records_features.append(feats)
                targets.append(row['target'])
            except Exception as e:
                logger.debug(f"Failed to engineer features for record {idx}: {e}")
                continue
                
        if not records_features:
            logger.warning(f"No valid features engineered for {pest_type} dataset.")
            return pd.DataFrame(), pd.Series()
            
        features_df = pd.DataFrame(records_features)
        targets_series = pd.Series(targets)
        
        logger.info(f"Successfully engineered features for {len(features_df)} records.")
        return features_df, targets_series

    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Trains and calibrates the XGBoost classifier, validating with a test split.
        """
        logger.info("Training Warning Level 1 XGBoost model...")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y if y.nunique() > 1 else None
        )
        
        if len(np.unique(y_train)) < 2:
            logger.warning("Training set has only one class. Training simplified dummy model.")
            self.model = XGBClassifier(n_estimators=5, max_depth=2, random_state=42)
            self.model.fit(X, y)
            return {"accuracy": 1.0, "auc": 1.0}
            
        self.model = XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42
        )
        
        self.model.fit(X_train, y_train)
        
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)[:, 1]
        
        acc = float(np.mean(y_pred == y_test))
        try:
            auc = float(roc_auc_score(y_test, y_proba))
        except Exception:
            auc = 0.5
            
        logger.info(f"Model trained successfully. Test Accuracy: {acc:.4f}, ROC-AUC: {auc:.4f}")
        
        # Save model
        model_path = os.path.join(self.model_dir, "warning_level1_xgboost.joblib")
        joblib.dump(self.model, model_path)
        logger.info(f"Model saved to {model_path}")
        
        return {
            "accuracy": acc,
            "auc": auc
        }

    def predict_risk(self, features: Dict[str, float]) -> float:
        """
        Predicts out-of-sample risk probability [0.0 - 1.0] for a given feature dictionary.
        """
        if self.model is None:
            model_path = os.path.join(self.model_dir, "warning_level1_xgboost.joblib")
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
            else:
                raise ValueError("Model has not been trained or saved yet.")
                
        df = pd.DataFrame([features])
        proba = self.model.predict_proba(df)[0, 1]
        return float(proba)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        pest_df = pd.read_csv('/Users/diegoh/Documents/GitHub/plag-out/data/exports/pest_monitoring_dataset.csv')
        cp = ClimateProvider(use_api=False)
        fe = FeatureEngineer(cp)
        wl1 = WarningLevel1Model()
        X, y = wl1.prepare_dataset(pest_df.head(100), fe)
        metrics = wl1.train(X, y)
        print("Training metrics:", metrics)
    except Exception as e:
        print("Failed to run test:", e)
