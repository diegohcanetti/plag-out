"""
Spatial Processing and Geocoding Layer

Provides high-precision geocoding for MAIZAR/SINAVIMO localities in Argentina.
Uses a local JSON-based persistent cache and falls back to Nominatim (OSM)
to geocode unknown coordinates while obeying usage limits.
"""

import os
import json
import logging
import time
from typing import Tuple, Dict, Optional
import requests

logger = logging.getLogger(__name__)

CACHE_FILE = "data/spatial_coords_cache.json"

# High-precision pre-populated agricultural coordinates in Argentina
DEFAULT_COORDS = {
    "pergamino_buenos aires": (-33.8899, -60.5696),
    "pozo de toba_santiago del estero": (-27.4667, -62.3167),
    "weisburd_santiago del estero": (-27.2833, -62.6167),
    "tolloche_salta": (-25.5500, -63.9500),
    "el carmen_jujuy": (-24.3833, -65.2500),
    "arroyo ceibal_santa fe": (-29.0167, -59.7167),
    "las lomitas_formosa": (-24.7081, -60.5931),
    "concepcion del bermejo_chaco": (-26.6000, -60.9500),
    "pampa del infierno_chaco": (-26.5052, -61.1744),
    "las breñas_chaco": (-27.0863, -61.0805),
    "juan josé castelli_chaco": (-25.9427, -60.6195),
    "tres isletas_chaco": (-26.3400, -60.4319),
    "gral. pinedo_chaco": (-27.3167, -61.2833),
}


class SpatialGeocoder:
    """
    Manages coordinate lookups and geocoding cache.
    """
    def __init__(self, cache_path: str = CACHE_FILE) -> None:
        self.cache_path = cache_path
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Tuple[float, float]]:
        """
        Loads the geocoding cache from disk, initializing with defaults if empty.
        """
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert values back to tuples
                    return {k: tuple(v) for k, v in data.items()}
            except Exception as e:
                logger.warning(f"Failed to load spatial cache: {e}. Using defaults.")
                
        # Initialize cache with defaults
        return DEFAULT_COORDS.copy()

    def _save_cache(self) -> None:
        """
        Saves the memory cache to disk.
        """
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to save spatial cache: {e}")

    def _clean_locality(self, locality: str) -> str:
        """
        Applies heuristic cleanup to strip trap/trial tags, expand abbreviations,
        and standardize common spelling issues.
        """
        import re
        loc = locality.replace("Gral.", "General")
        loc = loc.replace("gral.", "General")
        loc = loc.replace("J V ", "Joaquin V. ")
        loc = loc.replace("j v ", "Joaquin V. ")
        loc = loc.replace("Gonzales", "Gonzalez")
        loc = loc.replace("gonzales", "Gonzalez")
        loc = loc.replace("Fco ", "Francisco ")
        loc = loc.replace("fco ", "Francisco ")
        loc = loc.replace("S.M.", "San Martin")
        loc = loc.replace("S. M.", "San Martin")
        loc = loc.replace("S.F.", "San Francisco")
        loc = loc.replace("Sta.", "Santa")
        loc = loc.replace("sta.", "Santa")
        loc = loc.replace("Sto.", "Santo")
        loc = loc.replace("sto.", "Santo")
        
        # Strip trial/trap patterns like "T1", "T2", "T-3", etc.
        loc = re.sub(r"\b[Tt]\d+\b", "", loc)
        loc = re.sub(r"\bTraza\s*\d+\b", "", loc)
        
        # Strip specific trailing labels common in trial farms
        loc_lower = loc.lower()
        for tag in ["salesiana", "inta", "aapresid", "crea", "aappce", "agtsa"]:
            if loc_lower.endswith(f" {tag}"):
                loc = loc[:-(len(tag) + 1)]
                loc_lower = loc.lower()
                
        return " ".join(loc.strip().split())

    def geocode(self, locality: str, province: str) -> Tuple[float, float]:
        """
        Resolves the coordinates for a given locality and province in Argentina.
        First checks local cache, then queries Nominatim if not cached.
        
        Returns:
            Tuple[float, float]: (latitude, longitude) or province fallback if unresolved.
        """
        # Normalize keys to lower-case without double spaces
        loc_normalized = " ".join(locality.strip().lower().split())
        prov_normalized = " ".join(province.strip().lower().split())
        key = f"{loc_normalized}_{prov_normalized}"
        
        if key in self.cache:
            return self.cache[key]
            
        # Fallback to geocode using Nominatim API
        coords = self._query_nominatim(locality, province)
        if coords:
            self.cache[key] = coords
            self._save_cache()
            return coords
            
        # Province-level fallback coordinates to avoid (0.0, 0.0) which skips NASA POWER weather extraction
        province_coords = {
            "buenos aires": (-36.67, -60.50),
            "santa fe": (-30.90, -60.80),
            "entre ríos": (-32.10, -59.80),
            "entre rios": (-32.10, -59.80),
            "la pampa": (-36.60, -64.30),
            "san luis": (-33.80, -66.00),
            "jujuy": (-23.30, -65.70),
            "salta": (-24.70, -65.40),
            "tucumán": (-26.90, -65.20),
            "tucuman": (-26.90, -65.20),
            "catamarca": (-27.00, -66.00),
            "chaco": (-26.30, -60.80),
            "formosa": (-24.80, -59.80),
            "corrientes": (-28.50, -57.80),
            "córdoba": (-32.10, -63.60),
            "cordoba": (-32.10, -63.60),
            "santiago del estero": (-27.80, -64.30),
            "uruguay": (-32.50, -55.80),
        }
        
        prov_key = prov_normalized.strip()
        if prov_key in province_coords:
            fallback_coords = province_coords[prov_key]
            logger.warning(
                f"Could not geocode specific region: '{locality}, {province}'. "
                f"Applying province fallback coordinates: {fallback_coords}"
            )
            # Store in cache so we don't query Nominatim again for this key
            self.cache[key] = fallback_coords
            self._save_cache()
            return fallback_coords

        logger.warning(f"Could not geocode spatial region: {locality}, {province}. Returning (0.0, 0.0)")
        return 0.0, 0.0

    def _query_nominatim(self, locality: str, province: str) -> Optional[Tuple[float, float]]:
        """
        Queries OpenStreetMap Nominatim with a multi-tiered search strategy and polite delays.
        """
        cleaned_loc = self._clean_locality(locality)
        if not cleaned_loc:
            return None
            
        # Tier 1: "Cleaned Locality, Province, Argentina"
        # Tier 2: "Cleaned Locality, Argentina" (Handles cases where listed province is incorrect)
        # Tier 3: "Cleaned Locality" (Broadest fallback)
        search_queries = [
            f"{cleaned_loc}, {province}, Argentina",
            f"{cleaned_loc}, Argentina",
            cleaned_loc
        ]
        
        url = "https://nominatim.openstreetmap.org/search"
        headers = {
            "User-Agent": "Plag-out-Agrotech-Thesis-Pipeline-MVP/1.0 (diegoh@github.com)"
        }
        
        for query_str in search_queries:
            params = {
                "q": query_str,
                "format": "json",
                "limit": 1
            }
            logger.info(f"Querying Nominatim for: {query_str}")
            try:
                # Nominatim usage policy requires 1 second delay between requests
                time.sleep(1.0)
                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                if data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    logger.info(f"Geocoded successfully: {query_str} -> ({lat}, {lon})")
                    return lat, lon
            except Exception as e:
                logger.error(f"Nominatim geocoding failed for {query_str}: {e}")
                
        return None

