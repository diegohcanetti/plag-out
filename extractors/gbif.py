"""
GBIF Occurrences Extractor with Spatial Rarefaction

This module queries the Global Biodiversity Information Facility (GBIF) REST API
for species occurrence records and applies geographical cleaning filters,
including spatial rarefaction (retaining at most 1 record per 5x5 km grid cell).
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
import requests
import pandas as pd
from models.schemas import PestMonitoringRecord

logger = logging.getLogger(__name__)

GBIF_API_URL = "https://api.gbif.org/v1/occurrence/search"


def apply_spatial_rarefaction(
    records: List[PestMonitoringRecord],
    grid_size_km: float = 5.0
) -> List[PestMonitoringRecord]:
    """
    Applies spatial rarefaction: retains only one occurrence per grid cell.
    
    Args:
        records: List of raw records.
        grid_size_km: The grid cell size in kilometers. 
                      At the equator, 1 degree is ~111 km, so 5 km is ~0.045 degrees.
    """
    # 1 degree of latitude is ~111.32 km.
    # We use a simple grid size degree divisor:
    degree_delta = grid_size_km / 111.32
    
    unique_cells: Set[Tuple[int, int]] = set()
    rarefied_records = []
    
    for rec in records:
        if rec.latitude == 0.0 and rec.longitude == 0.0:
            continue
            
        # Compute grid cell indices by rounding
        grid_lat = int(round(rec.latitude / degree_delta))
        grid_lon = int(round(rec.longitude / degree_delta))
        cell_key = (grid_lat, grid_lon)
        
        if cell_key not in unique_cells:
            unique_cells.add(cell_key)
            rarefied_records.append(rec)
            
    logger.info(
        f"Spatial rarefaction complete: reduced from {len(records)} to "
        f"{len(rarefied_records)} records using a {grid_size_km}x{grid_size_km} km grid."
    )
    return rarefied_records


class GbifExtractor:
    """
    Client for querying species occurrences from GBIF with integrated cleaning.
    """
    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    def extract_occurrences(
        self,
        scientific_name: str,
        country_code: str = "AR",
        limit: int = 300,
        rarefy: bool = True
    ) -> List[PestMonitoringRecord]:
        """
        Fetches occurrences for a scientific name and transforms them.
        Uses pagination to handle limits cleanly.
        """
        logger.info(f"Querying GBIF for {scientific_name} in country {country_code}")
        
        records = []
        offset = 0
        batch_size = min(100, limit)
        
        while len(records) < limit:
            params = {
                "scientificName": scientific_name,
                "country": country_code,
                "limit": batch_size,
                "offset": offset,
                "hasCoordinate": "true"  # Ensure we only fetch records with valid lat/lon
            }
            
            try:
                response = requests.get(GBIF_API_URL, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                if not results:
                    break
                    
                for item in results:
                    lat = item.get("decimalLatitude")
                    lon = item.get("decimalLongitude")
                    
                    if lat is None or lon is None:
                        continue
                        
                    # Parse date
                    event_date_str = item.get("eventDate")
                    occurrence_date = datetime.now()  # Fallback
                    if event_date_str:
                        try:
                            # eventDate is typically ISO-8601, e.g., '2024-03-16T12:11:38'
                            occurrence_date = datetime.fromisoformat(event_date_str.split("Z")[0])
                        except Exception:
                            pass
                            
                    rec = PestMonitoringRecord(
                        occurrence_date=occurrence_date,
                        pest_type=scientific_name,
                        severity_level="Present",  # GBIF records presence
                        latitude=float(lat),
                        longitude=float(lon),
                        institution=item.get("institutionCode", "GBIF Occurrences"),
                        province=item.get("stateProvince", "Argentina"),
                        locality=item.get("locality", "Unknown"),
                        adults_count=1,
                        infection_percent=None
                    )
                    records.append(rec)
                    
                # Increment offset for pagination
                offset += len(results)
                
                # If we received fewer records than the batch size, we reached the end
                if len(results) < batch_size:
                    break
                    
            except Exception as e:
                logger.error(f"Error querying GBIF: {e}")
                break
                
        # Trim to exact limit
        records = records[:limit]
        
        if rarefy:
            return apply_spatial_rarefaction(records)
            
        return records


def extract_gbif_occurrences(
    scientific_name: str,
    country_code: str = "AR",
    limit: int = 300
) -> List[PestMonitoringRecord]:
    """
    Functional interface for the GBIF extractor.
    """
    client = GbifExtractor()
    return client.extract_occurrences(scientific_name, country_code, limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    recs = extract_gbif_occurrences("Spodoptera frugiperda", limit=10)
    print(f"Extracted {len(recs)} rarefied occurrences. Sample:")
    for r in recs[:2]:
        print(f"ID={r.pest_type} Date={r.occurrence_date} Location=({r.latitude:.4f}, {r.longitude:.4f}) Source={r.institution}")
