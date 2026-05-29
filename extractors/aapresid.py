"""
AAPRESID Insect Maps Extractor

This module reverse-engineers the AAPRESID REM (Red de Manejo de Plagas) interactive insect maps.
It queries the backend PHP endpoints directly using POST requests to extract presence
and percentage abundance data for Dalbulus maidis (Chicharrita) and Spodoptera frugiperda (Cogollero),
georeferences the results using department boundary centroids from their internal JSON,
and transforms them into PestMonitoringRecords.
"""

import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from models.schemas import PestMonitoringRecord

logger = logging.getLogger(__name__)

AAPRESID_API_URL = "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/_procesar_mapa.php"
DEPARTAMENTOS_JSON_URL = "https://www.aapresid.org.ar/rem-malezas/js/mapasDepartamentos/inc_departamentos.json"

# Map AAPRESID pest IDs to standardized scientific names
PEST_MAP = {
    # Dalbulus maidis
    "chicharrita-en-maiz-temprano": "Dalbulus maidis",
    "chicharrita-en-maiz-tardio": "Dalbulus maidis",
    
    # Spodoptera frugiperda
    "cogollero-en-maiz-temprano": "Spodoptera frugiperda",
    "cogollero-en-maiz-tardio": "Spodoptera frugiperda",
    "cogollero-en-maiz-temprano-no-bt": "Spodoptera frugiperda",
    "cogollero-en-maiz-temprano-bt-cry": "Spodoptera frugiperda",
    "cogollero-en-maiz-temprano-bt-vip": "Spodoptera frugiperda",
    "cogollero-en-maiz-tardio-no-bt": "Spodoptera frugiperda",
    "cogollero-en-maiz-tardio-bt-cry": "Spodoptera frugiperda",
    "cogollero-en-maiz-tardio-bt-vip": "Spodoptera frugiperda",

    # Helicoverpa zea
    "oruga-de-la-espiga-en-maiz-temprano": "Helicoverpa zea",
    "oruga-de-la-espiga-en-maiz-tardio": "Helicoverpa zea",

    # Faronta albilinea
    "oruga-desgranadora": "Faronta albilinea",
    "oruga-desgranadora-en-trigo": "Faronta albilinea",
}


def parse_centroid(coords_str: str) -> Tuple[float, float]:
    """
    Computes the centroid coordinate from the boundary points of a department.
    Boundary coordinates format: "longitude;latitude|longitude;latitude|..."
    """
    points = coords_str.strip().split("|")
    lats = []
    lons = []
    for p in points:
        if not p:
            continue
        parts = p.split(";")
        if len(parts) == 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                lats.append(lat)
                lons.append(lon)
            except ValueError:
                continue
    if lats and lons:
        return sum(lats) / len(lats), sum(lons) / len(lons)
    return 0.0, 0.0


def convert_season_to_date(season_str: str) -> datetime:
    """
    Converts a seasonal year string (e.g. '2023/2024') into a representative date
    for the mid-season peak (February 15 of the latter year).
    """
    try:
        parts = season_str.split("/")
        if len(parts) == 2:
            year = int(parts[1])
            return datetime(year, 2, 15)
    except Exception:
        pass
    return datetime.now()


class AapresidExtractor:
    """
    Extractor client for reverse engineering the AAPRESID REM map backend.
    """
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aapresid.org.ar",
            "Referer": "https://www.aapresid.org.ar/rem-malezas/mapa-insectos/"
        })
        self._deptos_map: Dict[str, Dict] = {}

    def fetch_departments(self) -> Dict[str, Dict]:
        """
        Fetches the department mappings including names, provinces, and boundary coordinates.
        """
        if self._deptos_map:
            return self._deptos_map
            
        logger.info(f"Downloading department boundary definitions from {DEPARTAMENTOS_JSON_URL}...")
        try:
            res = self.session.get(DEPARTAMENTOS_JSON_URL, timeout=30)
            res.raise_for_status()
            self._deptos_map = res.json()
            logger.info(f"Successfully loaded definitions for {len(self._deptos_map)} departments.")
        except Exception as e:
            logger.error(f"Failed to fetch departments JSON: {e}")
            raise
        return self._deptos_map

    def fetch_presence_data(self, seasons: List[str]) -> List[PestMonitoringRecord]:
        """
        Queries the Presence map ('presencia_maleza') API endpoint.
        """
        logger.info("Fetching presence map records from AAPRESID REM API...")
        
        # Determine all pest identifiers we are interested in
        pests = [
            "chicharrita-en-maiz-temprano",
            "chicharrita-en-maiz-tardio",
            "cogollero-en-maiz-temprano",
            "cogollero-en-maiz-tardio",
            "oruga-de-la-espiga-en-maiz-temprano",
            "oruga-de-la-espiga-en-maiz-tardio",
            "oruga-desgranadora",
            "oruga-desgranadora-en-trigo"
        ]
        
        # Build multipart URL-encoded POST tuples to handle array parameters correctly
        data_tuples = [
            ("accion", "procesar_form"),
            ("tipo_mapa", "presencia_maleza"),
        ]
        for p in pests:
            data_tuples.append(("malezas[]", p))
        for s in seasons:
            data_tuples.append(("anosPM[]", s))
            
        records = []
        try:
            res = self.session.post(AAPRESID_API_URL, data=data_tuples, timeout=30)
            res.raise_for_status()
            data = res.json()
            
            # Fetch geocoding boundaries
            deptos_ref = self.fetch_departments()
            
            # Parse response. aDeptoMalezas contains lists of records grouped by department id
            adepto_malezas = data.get("aDeptoMalezas", {})
            for depto_id, pest_list in adepto_malezas.items():
                ref = deptos_ref.get(str(depto_id))
                if not ref:
                    continue
                    
                prov = ref.get("provincia", "Unknown").title()
                locality = ref.get("departamento", "Unknown").title()
                lat, lon = parse_centroid(ref.get("coordenadas", ""))
                
                for item in pest_list:
                    pest_id = item.get("id_maleza")
                    standard_pest = PEST_MAP.get(pest_id)
                    if not standard_pest:
                        continue
                        
                    # Check presence value for each season
                    for season in seasons:
                        val = item.get(season)
                        if val == 1:  # 1 indicates Present
                            occ_date = convert_season_to_date(season)
                            records.append(PestMonitoringRecord(
                                occurrence_date=occ_date,
                                pest_type=standard_pest,
                                severity_level="Present (Qualitative REM Presence Map)",
                                latitude=lat,
                                longitude=lon,
                                institution="AAPRESID (REM Map)",
                                province=prov,
                                locality=locality,
                                adults_count=None,
                                infection_percent=None
                            ))
                            
            logger.info(f"Extracted {len(records)} presence records from AAPRESID map.")
        except Exception as e:
            logger.error(f"Error querying AAPRESID presence data: {e}")
            
        return records

    def fetch_abundance_data(self, seasons: List[str]) -> List[PestMonitoringRecord]:
        """
        Queries the Abundance/Superficie tratada ('abundancia_maleza') API endpoint.
        """
        logger.info("Fetching abundance/treated-area records from AAPRESID REM API...")
        
        # Abundance maps are queried per pest. We'll iterate through our target pests.
        abundance_pests = [
            "chicharrita-en-maiz-temprano",
            "chicharrita-en-maiz-tardio",
            "cogollero-en-maiz-temprano-no-bt",
            "cogollero-en-maiz-temprano-bt-cry",
            "cogollero-en-maiz-temprano-bt-vip",
            "cogollero-en-maiz-tardio-no-bt",
            "cogollero-en-maiz-tardio-bt-cry",
            "cogollero-en-maiz-tardio-bt-vip",
            "oruga-de-la-espiga-en-maiz-temprano",
            "oruga-de-la-espiga-en-maiz-tardio",
            "oruga-desgranadora",
            "oruga-desgranadora-en-trigo"
        ]
        
        records = []
        try:
            deptos_ref = self.fetch_departments()
            
            for pest_id in abundance_pests:
                logger.info(f"Querying abundance for pest ID: {pest_id}...")
                
                # Build tuples
                data_tuples = [
                    ("accion", "procesar_form"),
                    ("tipo_mapa", "abundancia_maleza"),
                    ("maleza[]", pest_id)
                ]
                for s in seasons:
                    data_tuples.append(("anosMapaAbundancia[]", s))
                    
                res = self.session.post(AAPRESID_API_URL, data=data_tuples, timeout=30)
                res.raise_for_status()
                data = res.json()
                
                # Parse response. Key: aMalezaDeptoMediciones -> season -> pest_id -> dict of dept_id -> record
                meds = data.get("aMalezaDeptoMediciones", {})
                for season in seasons:
                    season_data = meds.get(season, {})
                    pest_data = season_data.get(pest_id, {})
                    
                    if not pest_data:
                        continue
                        
                    standard_pest = PEST_MAP.get(pest_id)
                    occ_date = convert_season_to_date(season)
                    
                    # pest_data is a dict of depto_id -> record
                    for depto_id, rec_data in pest_data.items():
                        porc_val = rec_data.get("porc_maleza")
                        if porc_val is None:
                            continue
                            
                        porc = float(porc_val)
                        if porc == 0.0:
                            # 0% affected indicates Absence or negligible population
                            continue
                            
                        ref = deptos_ref.get(str(depto_id))
                        if not ref:
                            continue
                            
                        prov = ref.get("provincia", "Unknown").title()
                        locality = ref.get("departamento", "Unknown").title()
                        lat, lon = parse_centroid(ref.get("coordenadas", ""))
                        
                        # Translate percentage to qualitative severity level
                        if porc <= 20.0:
                            sev = f"Low ({porc}% lots affected)"
                        elif porc <= 50.0:
                            sev = f"Medium ({porc}% lots affected)"
                        else:
                            sev = f"High ({porc}% lots affected)"
                            
                        records.append(PestMonitoringRecord(
                            occurrence_date=occ_date,
                            pest_type=standard_pest,
                            severity_level=sev,
                            latitude=lat,
                            longitude=lon,
                            institution="AAPRESID (REM Map)",
                            province=prov,
                            locality=locality,
                            adults_count=None,
                            infection_percent=porc
                        ))
                        
            logger.info(f"Extracted {len(records)} abundance records from AAPRESID map.")
        except Exception as e:
            logger.error(f"Error querying AAPRESID abundance data: {e}")
            
        return records

    def extract_aapresid_records(self, seasons: List[str] = None) -> List[PestMonitoringRecord]:
        """
        Runs both presence and abundance queries and merges them to create a unified, robust dataset.
        """
        if seasons is None:
            # We want all available seasons including the critical 2023/2024 cycle
            seasons = ["2023/2024", "2021/2022", "2019/2020"]
            
        logger.info(f"Starting complete AAPRESID extraction for seasons: {seasons}...")
        
        presence_recs = self.fetch_presence_data(seasons)
        abundance_recs = self.fetch_abundance_data(seasons)
        
        # Merge records. We index them by (pest_type, province, locality, occurrence_date)
        merged_dict: Dict[Tuple[str, str, str, datetime], PestMonitoringRecord] = {}
        
        # Add presence records first
        for rec in presence_recs:
            key = (rec.pest_type, rec.province, rec.locality, rec.occurrence_date)
            merged_dict[key] = rec
            
        # Overwrite/update with abundance records (since abundance has percentage and better severity descriptions)
        for rec in abundance_recs:
            key = (rec.pest_type, rec.province, rec.locality, rec.occurrence_date)
            if key in merged_dict:
                # Update existing presence record with precise percentage and severity
                existing = merged_dict[key]
                existing.severity_level = rec.severity_level
                existing.infection_percent = rec.infection_percent
            else:
                # Add new record
                merged_dict[key] = rec
                
        final_records = list(merged_dict.values())
        logger.info(f"AAPRESID extraction completed: merged into {len(final_records)} unique records.")
        return final_records


def extract_aapresid_data(seasons: List[str] = None) -> List[PestMonitoringRecord]:
    """
    Functional entry point for the AAPRESID extractor.
    """
    extractor = AapresidExtractor()
    return extractor.extract_aapresid_records(seasons)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    recs = extract_aapresid_data(["2023/2024"])
    print(f"\nExtracted {len(recs)} records. Sample:")
    for r in recs[:5]:
        print(f"Pest={r.pest_type} Date={r.occurrence_date.date()} Locality={r.locality} Prov={r.province} Severity={r.severity_level} Infection={r.infection_percent}%")
