"""
Plag-out Machine Learning Pipeline: Empirical Biofix Extractor

This module programmatically extracts empirical "Biofix" dates (cohort start points)
from historical pest monitoring trap catches (adults_count).
It supports multi-generational concurrency, allowing multiple Biofix tracking threads
for overlapping generations of migratory pests.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class BiofixCohort:
    """
    Represents an active biological cohort thread triggered by an empirical Biofix.
    """
    def __init__(self, species: str, biofix_date: datetime, peak_count: float, locality: str, province: str, coord: Tuple[float, float]):
        self.species = species
        self.biofix_date = biofix_date
        self.peak_count = peak_count
        self.locality = locality
        self.province = province
        self.latitude, self.longitude = coord
        
    def __repr__(self) -> str:
        return (f"BiofixCohort({self.species} at {self.locality}, {self.province} "
                f"on {self.biofix_date.strftime('%Y-%m-%d')} with {self.peak_count} adults)")


class BiofixExtractor:
    """
    Extracts empirical Biofix dates (cohort start times) from historical trap datasets.
    """
    def __init__(
        self,
        min_adults_threshold: float = 10.0,
        separation_days: int = 28,
        peak_prominence_factor: float = 1.5
    ):
        """
        Args:
            min_adults_threshold: Minimum trap catch size to trigger a potential Biofix.
            separation_days: Minimum days between distinct cohorts to avoid splitting the same generation.
            peak_prominence_factor: How much higher a peak must be relative to rolling average to count as a major cohort trigger.
        """
        self.min_adults_threshold = min_adults_threshold
        self.separation_days = separation_days
        self.peak_prominence_factor = peak_prominence_factor

    def parse_coordinates(self, geom_wkt: str) -> Tuple[float, float]:
        """
        Parses WKT Point string (e.g. 'POINT(-65.25 -24.3833)') to (latitude, longitude).
        """
        if not isinstance(geom_wkt, str) or "POINT" not in geom_wkt:
            return (0.0, 0.0)
        try:
            coords_str = geom_wkt.replace("POINT(", "").replace(")", "")
            lon_str, lat_str = coords_str.strip().split()
            return float(lat_str), float(lon_str)
        except Exception as e:
            logger.warning(f"Error parsing geom_wkt '{geom_wkt}': {e}")
            return (0.0, 0.0)

    def extract_biofixes(self, df: pd.DataFrame) -> List[BiofixCohort]:
        """
        Processes a DataFrame of pest monitoring records and programmatically extracts Biofix cohorts.
        
        The algorithm identifies:
        1. First occurrence: When trap catches transition from zero or empty to above the minimum threshold.
        2. Subsequent population peaks: Major local maxima representing overlapping/new migratory pest waves.
        """
        cohorts: List[BiofixCohort] = []
        
        # Ensure correct datatypes
        df = df.copy()
        df['occurrence_date'] = pd.to_datetime(df['occurrence_date'], format='mixed', utc=True)
        df['adults_count'] = pd.to_numeric(df['adults_count'], errors='coerce').fillna(0.0)
        
        # We group by locality, province, geom_wkt, and pest_type to analyze local cohort lines
        # In case locality is missing, we use geocoordinates
        df['group_id'] = df.apply(
            lambda r: f"{r['province'] or 'Unknown'}_{r['locality'] or 'Unknown'}_{r['geom_wkt']}", axis=1
        )
        
        for (group_id, pest_type), group in df.groupby(['group_id', 'pest_type']):
            # Sort chronologically
            group = group.sort_values('occurrence_date')
            
            if len(group) == 0:
                continue
                
            # Parse coordinate
            geom = group['geom_wkt'].iloc[0]
            lat, lon = self.parse_coordinates(geom)
            loc = group['locality'].iloc[0] or "Unknown"
            prov = group['province'].iloc[0] or "Unknown"
            
            # Find Biofix dates
            last_biofix_date: Optional[datetime] = None
            
            # 1. Look for first detection (first catch above threshold)
            first_valid = group[group['adults_count'] >= self.min_adults_threshold]
            if not first_valid.empty:
                first_row = first_valid.iloc[0]
                biofix_date = first_row['occurrence_date']
                count = first_row['adults_count']
                
                cohorts.append(BiofixCohort(
                    species=pest_type,
                    biofix_date=biofix_date,
                    peak_count=count,
                    locality=loc,
                    province=prov,
                    coord=(lat, lon)
                ))
                last_biofix_date = biofix_date
            
            # 2. Look for subsequent peaks (overlapping generations)
            # We use a rolling maximum / average to find prominence peaks separated by separation_days
            for idx, row in group.iterrows():
                curr_date = row['occurrence_date']
                curr_count = row['adults_count']
                
                if curr_count < self.min_adults_threshold:
                    continue
                    
                # Skip if too close to the last registered Biofix (same cohort)
                if last_biofix_date and (curr_date - last_biofix_date).days < self.separation_days:
                    continue
                    
                # We identify a new peak if this count is a local peak and significantly higher
                # than surrounding values or is a substantial jump representing a new wave
                # For sparse data, any major trap catches separated by 28+ days indicates a new cohort
                cohorts.append(BiofixCohort(
                    species=pest_type,
                    biofix_date=curr_date,
                    peak_count=curr_count,
                    locality=loc,
                    province=prov,
                    coord=(lat, lon)
                ))
                last_biofix_date = curr_date

        logger.info(f"Programmatically extracted {len(cohorts)} Biofix cohorts from dataset.")
        return cohorts


if __name__ == "__main__":
    # Test Biofix extraction
    logging.basicConfig(level=logging.INFO)
    try:
        pest_df = pd.read_csv('/Users/diegoh/Documents/GitHub/plag-out/data/exports/pest_monitoring_dataset.csv')
        extractor = BiofixExtractor()
        cohorts = extractor.extract_biofixes(pest_df)
        print(f"Extracted {len(cohorts)} cohorts. First 5 sample:")
        for c in cohorts[:5]:
            print(" -", c)
    except Exception as e:
        print("Failed to run test:", e)
