"""
Unit Tests for Phase 1 Extractors (AAPRESID & PowerBI)
"""

import unittest
from datetime import datetime
from extractors.aapresid import parse_centroid, convert_season_to_date, PEST_MAP
from extractors.powerbi_maiz import clean_salida, parse_period, get_province_for_unit

class TestNewExtractors(unittest.TestCase):
    
    def test_parse_centroid(self):
        """
        Tests coordinate centroid calculation for department boundaries.
        """
        # Format: "longitude;latitude|longitude;latitude"
        coords_str = "-60.869;-35.8405|-60.7897;-35.9045"
        lat, lon = parse_centroid(coords_str)
        
        # Expected:
        # Lat = (-35.8405 + -35.9045) / 2 = -35.8725
        # Lon = (-60.869 + -60.7897) / 2 = -60.82935
        self.assertAlmostEqual(lat, -35.8725)
        self.assertAlmostEqual(lon, -60.82935)
        
        # Test empty coordinates handles cleanly
        lat_empty, lon_empty = parse_centroid("")
        self.assertEqual(lat_empty, 0.0)
        self.assertEqual(lon_empty, 0.0)

    def test_convert_season_to_date(self):
        """
        Tests season strings to standard peak date translation.
        """
        d = convert_season_to_date("2023/2024")
        self.assertEqual(d.year, 2024)
        self.assertEqual(d.month, 2, "Peak season should be in February")
        self.assertEqual(d.day, 15)

    def test_pest_mapping(self):
        """
        Tests mapping of AAPRESID identifiers to scientific names.
        """
        self.assertEqual(PEST_MAP["chicharrita-en-maiz-temprano"], "Dalbulus maidis")
        self.assertEqual(PEST_MAP["cogollero-en-maiz-tardio-bt-vip"], "Spodoptera frugiperda")

    def test_clean_salida(self):
        """
        Tests parsing of PowerBI text count output.
        """
        total, label = clean_salida("Hembras: 0,09; Machos: 0,04 (Indvs./golpe de red)")
        self.assertAlmostEqual(total, 0.13)
        self.assertEqual(label, "Hembras: 0.09; Machos: 0.04")

        # Handles empty/invalid strings gracefully
        total_none, label_raw = clean_salida("Unknown status")
        self.assertIsNone(total_none)
        self.assertEqual(label_raw, "Unknown status")

    def test_parse_period(self):
        """
        Tests parsing of weekly period strings.
        """
        d = parse_period("2024 - JUN 3 – JUN 9")
        self.assertEqual(d.year, 2024)
        self.assertEqual(d.month, 6)
        self.assertEqual(d.day, 3)

    def test_get_province_for_unit(self):
        """
        Tests mapping of INTA Unit names to provinces.
        """
        self.assertEqual(get_province_for_unit("EEA Anguil"), "La Pampa")
        self.assertEqual(get_province_for_unit("AER Huinca Renancó"), "Córdoba")
        self.assertEqual(get_province_for_unit("UI INTA Balcarce - UNMdP"), "Buenos Aires")
        self.assertEqual(get_province_for_unit("EEA Concepción del Uruguay"), "Entre Ríos")
        self.assertEqual(get_province_for_unit("EEA El Colorado"), "Formosa")
        self.assertEqual(get_province_for_unit("Unknown station"), "Argentina")

if __name__ == "__main__":
    unittest.main()
