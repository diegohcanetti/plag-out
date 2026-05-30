"""
Unit Tests for Phase 4 Data Quality Gates and Quarantine System
"""

import unittest
from datetime import datetime
import pandas as pd
import pytest
from sqlalchemy import text

from orchestrator import validate_pest_records_dataframe
from loaders.db import get_engine, quarantine_failed_file


class TestDataQualityGates(unittest.TestCase):
    
    def test_valid_south_america_records(self):
        """
        Verify that a valid South American record passes the quality gate.
        """
        valid_df = pd.DataFrame([{
            "occurrence_date": datetime(2026, 5, 30),
            "latitude": -34.6037,  # Buenos Aires
            "longitude": -58.3816,
            "pest_type": "Dalbulus maidis",
            "severity_level": "Low"
        }])
        
        # Should execute successfully without throwing AssertionError
        validate_pest_records_dataframe(valid_df)

    def test_out_of_bounds_coordinates(self):
        """
        Verify that coordinates outside South America throw AssertionError.
        """
        # North America / Africa bounds (out of SA bounds)
        invalid_lat_df = pd.DataFrame([{
            "occurrence_date": datetime(2026, 5, 30),
            "latitude": 40.7128,  # New York
            "longitude": -74.0060,
            "pest_type": "Dalbulus maidis",
            "severity_level": "Low"
        }])
        
        with self.assertRaises(AssertionError):
            validate_pest_records_dataframe(invalid_lat_df)
            
        # Ocean / 0.0 coordinate failure (e.g. failed geocoding)
        zero_coord_df = pd.DataFrame([{
            "occurrence_date": datetime(2026, 5, 30),
            "latitude": 0.0,
            "longitude": 0.0,
            "pest_type": "Dalbulus maidis",
            "severity_level": "Low"
        }])
        
        with self.assertRaises(AssertionError):
            validate_pest_records_dataframe(zero_coord_df)

    def test_missing_and_null_columns(self):
        """
        Verify that missing or null critical columns throw AssertionError.
        """
        # Null occurrence date
        null_date_df = pd.DataFrame([{
            "occurrence_date": None,
            "latitude": -34.6037,
            "longitude": -58.3816,
            "pest_type": "Dalbulus maidis",
            "severity_level": "Low"
        }])
        
        with self.assertRaises(AssertionError):
            validate_pest_records_dataframe(null_date_df)

        # Missing latitude column entirely
        missing_col_df = pd.DataFrame([{
            "occurrence_date": datetime(2026, 5, 30),
            "longitude": -58.3816,
            "pest_type": "Dalbulus maidis",
            "severity_level": "Low"
        }])
        
        with self.assertRaises(AssertionError):
            validate_pest_records_dataframe(missing_col_df)

    def test_quarantine_database_insertion(self):
        """
        Verify that quarantine_failed_file inserts logs into the etl_quarantine table.
        """
        engine = get_engine()
        test_file = "data/maizar_pdfs/corrupted_test_report.pdf"
        test_error = "TestDataQualityGates AssertionError: Coordinate values out of bounds."
        
        # Ingest failed file to quarantine
        quarantine_failed_file(test_file, test_error)
        
        # Verify the record exists in database
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT file_path, error_message FROM etl_quarantine WHERE file_path = :file"),
                {"file": test_file}
            ).fetchall()
            
        self.assertGreater(len(result), 0, "No quarantined records found in database!")
        self.assertEqual(result[-1][0], test_file)
        self.assertEqual(result[-1][1], test_error)
        
        # Clean up database entry
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM etl_quarantine WHERE file_path = :file"),
                {"file": test_file}
            )


if __name__ == "__main__":
    unittest.main()
