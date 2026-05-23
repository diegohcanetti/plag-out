"""
Unit and Integration Tests for Plag-out ML & Thermodynamic Pipeline
"""

import unittest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from ml.biofix import BiofixExtractor, BiofixCohort
from ml.climate import ClimateProvider, GDDCalculator
from ml.predictors import FeatureEngineer
from ml.engine import ThermodynamicEngine


class TestMLPipeline(unittest.TestCase):
    def setUp(self):
        self.cp = ClimateProvider(use_api=False)
        self.gdd_calc = GDDCalculator()
        self.engine = ThermodynamicEngine(self.cp)
        self.fe = FeatureEngineer(self.cp)

    def test_gdd_calculation(self):
        """
        Tests standard Growing Degree Days formulas.
        """
        # Scenario A: Mean temp exceeds base
        gdd = self.gdd_calc.calculate_daily_gdd(tmax=25.0, tmin=15.0, tbase=10.0)
        self.assertEqual(gdd, 10.0)  # (25+15)/2 - 10 = 10.0

        # Scenario B: Temperature falls below base
        gdd = self.gdd_calc.calculate_daily_gdd(tmax=8.0, tmin=4.0, tbase=10.0)
        self.assertEqual(gdd, 0.0)  # Tmax and Tmin clipped to tbase -> (10+10)/2 - 10 = 0.0

        # Scenario C: Upper cutoff constraint
        gdd = self.gdd_calc.calculate_daily_gdd(tmax=35.0, tmin=15.0, tbase=10.0, tupper=30.0)
        self.assertEqual(gdd, 12.5)  # (30+15)/2 - 10 = 12.5 (35 clipped to 30)

    def test_biofix_extractor(self):
        """
        Tests empirical Biofix parsing and coordinates extraction.
        """
        be = BiofixExtractor(min_adults_threshold=10.0)
        
        # Test coordinates parsing
        lat, lon = be.parse_coordinates("POINT(-65.25 -24.3833)")
        self.assertAlmostEqual(lat, -24.3833)
        self.assertAlmostEqual(lon, -65.25)
        
        # Test mock dataset extraction
        data = {
            'occurrence_date': ['2026-01-01', '2026-01-05', '2026-02-15'],
            'pest_type': ['Dalbulus maidis', 'Dalbulus maidis', 'Dalbulus maidis'],
            'severity_level': ['Present', 'High', 'Present'],
            'province': ['Jujuy', 'Jujuy', 'Jujuy'],
            'locality': ['EL Carmen', 'EL Carmen', 'EL Carmen'],
            'adults_count': [2.0, 45.0, 12.0],
            'geom_wkt': ['POINT(-65.25 -24.3833)', 'POINT(-65.25 -24.3833)', 'POINT(-65.25 -24.3833)']
        }
        df = pd.DataFrame(data)
        cohorts = be.extract_biofixes(df)
        
        # Should extract 2 cohorts (first peak on Jan 5, second peak on Feb 15 since it is > 28 days later)
        self.assertEqual(len(cohorts), 2)
        self.assertEqual(cohorts[0].species, "Dalbulus maidis")
        self.assertEqual(cohorts[0].locality, "EL Carmen")
        self.assertAlmostEqual(cohorts[0].peak_count, 45.0)

    def test_thermodynamic_engine(self):
        """
        Tests biological lifecycle cohort tracking.
        """
        cohort = BiofixCohort(
            species="Dalbulus maidis",
            biofix_date=datetime(2026, 1, 1),
            peak_count=100.0,
            locality="EL Carmen",
            province="Jujuy",
            coord=(-24.3833, -65.25)
        )
        
        report = self.engine.track_cohort(cohort, datetime(2026, 1, 15))
        self.assertEqual(report["status"], "Active")
        self.assertGreater(report["accumulated_gdd"], 0.0)
        self.assertIn(report["threat_level"], ["Low", "Warning", "Critical", "Info"])

    def test_feature_engineering(self):
        """
        Tests spatial-temporal lag features extraction.
        """
        feats = self.fe.engineer_features_for_record(
            lat=-34.0, lon=-60.0,
            target_date=datetime(2026, 3, 1),
            planting_date=datetime(2026, 1, 1)
        )
        
        self.assertIn("gdd_accum_planting", feats)
        self.assertIn("temp_max_mean_7d", feats)
        self.assertIn("humidity_mean_14d", feats)
        self.assertIn("precip_sum_7d", feats)


if __name__ == "__main__":
    unittest.main()
