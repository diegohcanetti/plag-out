"""
PowerBI Chicharrita Dashboard Extractor

This module uses Playwright to open the public Microsoft PowerBI dashboard for the 
National Monitoring Red of Dalbulus maidis (Chicharrita del Maíz) in Argentina.
It intercepts the dynamic querydata JSON responses, decodes the PowerBI run-length encoding
compressed rows, georeferences the INTA units, and normalizes them into PestMonitoringRecords.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from playwright.async_api import async_playwright
from models.schemas import PestMonitoringRecord
from transformers.spatial import SpatialGeocoder

logger = logging.getLogger(__name__)

DASHBOARD_URL = "https://app.powerbi.com/view?r=eyJrIjoiZDMxMjRkZmItMDA4Ny00NjIzLWFkNjUtYzU3OGZjNjlkMjc4IiwidCI6IjE5MTBjMTYzLTY0YWUtNGZhMC1iY2QyLTBjMThiNzNkMmZiYSIsImMiOjR9"


def get_province_for_unit(unit: str) -> str:
    """
    Heuristic helper to map an INTA unit name to its proper Argentinian province
    so that the geocoder has accurate spatial context.
    """
    # Normalize all whitespaces (including \xa0 non-breaking spaces)
    unit = " ".join(unit.strip().split())
    unit_lower = unit.lower()
    
    # Santa Fe
    if any(x in unit_lower for x in ["oliveros", "reconquista", "villa minetti", "rafaela", "casilda", "tostado", "las toscas", "calchaquí", "san javier", "gálvez", "ceres", "san cristóbal", "castellanos", "san justo", "totoras", "roldán", "monte vera", "carlos pellegrini", "las rosas", "esperanza"]):
        return "Santa Fe"
    
    # Córdoba
    if any(x in unit_lower for x in ["huinca renancó", "manfredi", "marcos juárez", "adelia maría", "corral de bustos", "la carlota", "jesús maría", "laboulaye", "justiniano posse", "córdoba", "san francisco", "déan funes", "río seco", "brinkmann", "río primero"]):
        return "Córdoba"
        
    # Buenos Aires
    if any(x in unit_lower for x in ["balcarce", "bordenave", "pergamino", "hilario ascasubi", "san antonio de areco", "chivilcoy", "zarate", "san pedro", "villegas", "trenque lauquen", "lincoln", "bolívar", "pehuajó", "junín", "san nicolás", "colón"]):
        return "Buenos Aires"
        
    # Entre Ríos
    if any(x in unit_lower for x in ["concepción del uruguay", "paraná", "crespo", "diamante", "la paz", "san salvador", "feliciano", "victoria", "villaguay", "nogoyá", "federal", "gualeguay", "concordia", "gualeguaychú"]):
        return "Entre Ríos"
        
    # Tucumán
    if any(x in unit_lower for x in ["trancas", "aguilares", "banda del río salí", "graneros"]):
        return "Tucumán"
        
    # Salta
    if any(x in unit_lower for x in ["metán", "salta"]):
        return "Salta"
        
    # San Luis
    if any(x in unit_lower for x in ["san luis", "quines"]):
        return "San Luis"
        
    # La Pampa
    if any(x in unit_lower for x in ["anguil", "guatraché"]):
        return "La Pampa"
        
    # Others
    if "catamarca" in unit_lower:
        return "Catamarca"
    if "el colorado" in unit_lower:
        return "Formosa"
    if "las breñas" in unit_lower:
        return "Chaco"
    if "quimilí" in unit_lower:
        return "Santiago del Estero"
    if "yuto" in unit_lower:
        return "Jujuy"
        
    return "Argentina"


def clean_salida(salida_str: str) -> Tuple[Optional[float], str]:
    """
    Parses 'Hembras: X,XX; Machos: Y,YY' to return total density count and clean label.
    """
    if not salida_str:
        return None, ""
    try:
        # e.g., 'Hembras: 0,09; Machos: 0,04 (Indvs./golpe de red)'
        match = re.search(r'Hembras:\s*([\d,]+);\s*Machos:\s*([\d,]+)', salida_str)
        if match:
            h_str = match.group(1).replace(",", ".")
            m_str = match.group(2).replace(",", ".")
            h = float(h_str)
            m = float(m_str)
            return h + m, f"Hembras: {h}; Machos: {m}"
    except Exception:
        pass
    return None, salida_str


def parse_period(period_str: str) -> datetime:
    """
    Parses '2024 - JUN 3 – JUN 9' to get the starting date of the week.
    """
    months_es_en = {
        'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
    }
    try:
        match = re.search(r'(\d{4})\s*-\s*([A-Z]{3})\s*(\d+)', period_str)
        if match:
            year = int(match.group(1))
            month_str = match.group(2)
            day = int(match.group(3))
            month = months_es_en.get(month_str, 6)
            return datetime(year, month, day)
    except Exception:
        pass
    return datetime.now()


class PowerBiMaizExtractor:
    """
    Headless browser automated client to intercept and decode PowerBI records.
    """
    def __init__(self) -> None:
        self.geocoder = SpatialGeocoder()

    async def _intercept_querydata_responses(self) -> List[Dict]:
        """
        Launches Playwright and captures the JSON payloads of wabi querydata requests.
        """
        querydata_payloads = []
        
        async with async_playwright() as p:
            logger.info("Launching headless Chromium browser for PowerBI...")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            async def handle_response(response):
                if "querydata" in response.url:
                    try:
                        text = await response.text()
                        json_data = json.loads(text)
                        querydata_payloads.append(json_data)
                    except Exception as e:
                        logger.warning(f"Failed to read querydata response: {e}")
                        
            page.on("response", handle_response)
            
            logger.info(f"Navigating to PowerBI public dashboard: {DASHBOARD_URL}")
            await page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=60000)
            
            # Let the lazy widgets fully render
            await asyncio.sleep(12)
            await browser.close()
            
        logger.info(f"Captured {len(querydata_payloads)} wabi querydata responses.")
        return querydata_payloads

    def _decode_powerbi_rows(self, querydata_responses: List[Dict], limit: Optional[int] = None) -> List[PestMonitoringRecord]:
        """
        Decodes wabi querydata response shapes to reconstruct logical records.
        """
        records = []
        target_payload = None
        
        # Locate the querydata payload containing D0, D1, D2 value dictionaries
        for res in querydata_responses:
            try:
                results = res.get("results", [])
                if results:
                    ds_list = results[0].get("result", {}).get("data", {}).get("dsr", {}).get("DS", [])
                    if ds_list:
                        vd = ds_list[0].get("ValueDicts", {})
                        if "D0" in vd and "D1" in vd and "D2" in vd:
                            target_payload = ds_list[0]
                            break
            except Exception:
                continue
                
        if not target_payload:
            logger.error("Could not find the target querydata response containing INTA data dictionaries!")
            return []
            
        value_dicts = target_payload["ValueDicts"]
        d0_units = value_dicts.get("D0", [])
        d1_counts = value_dicts.get("D1", [])
        d2_periods = value_dicts.get("D2", [])
        
        dm0_rows = target_payload["PH"][0]["DM0"]
        logger.info(f"Decoding {len(dm0_rows)} compressed PowerBI rows...")
        
        current_row = [None, None, None, None]
        
        for idx, item in enumerate(dm0_rows):
            if limit is not None and len(records) >= limit:
                break
                
            c_vals = item.get("C", [])
            for i, val in enumerate(c_vals):
                current_row[i] = val
                
            row_copy = list(current_row)
            
            # Reconstruct indices
            unit_idx = row_copy[1]
            salida_idx = row_copy[2]
            period_idx = row_copy[3]
            
            # Validate indices
            if unit_idx is None or unit_idx >= len(d0_units):
                continue
            if salida_idx is None or salida_idx >= len(d1_counts):
                continue
            if period_idx is None or period_idx >= len(d2_periods):
                continue
                
            unit_name = d0_units[unit_idx]
            salida_val = d1_counts[salida_idx]
            period_val = d2_periods[period_idx]
            
            # Parse values
            occ_date = parse_period(period_val)
            total_density, clean_sal = clean_salida(salida_val)
            
            # Determine province and geocode
            prov = get_province_for_unit(unit_name)
            search_name = unit_name if "inta" in unit_name.lower() else f"INTA {unit_name}"
            lat, lon = self.geocoder.geocode(search_name, prov)
            
            if lat == 0.0 or lon == 0.0:
                logger.warning(f"Unresolved geocoding for {search_name} ({prov}). Skipping record.")
                continue
                
            # Determine qualitative severity
            if total_density is not None:
                if total_density == 0.0:
                    sev = "Absent"
                elif total_density <= 0.1:
                    sev = f"Low ({total_density:.2f} Indvs/golpe)"
                elif total_density <= 0.5:
                    sev = f"Medium ({total_density:.2f} Indvs/golpe)"
                else:
                    sev = f"High ({total_density:.2f} Indvs/golpe)"
            else:
                sev = "Present"
                
            # Add record. infection_percent represents density (Indvs./golpe de red)
            rec = PestMonitoringRecord(
                occurrence_date=occ_date,
                pest_type="Dalbulus maidis",
                severity_level=sev,
                latitude=lat,
                longitude=lon,
                institution="Red Nacional de Monitoreo Dalbulus maidis",
                province=prov,
                locality=unit_name,
                adults_count=int(round(total_density)) if total_density is not None else None,
                infection_percent=total_density
            )
            records.append(rec)
            
        logger.info(f"Reconstructed and validated {len(records)} records from PowerBI dashboard.")
        return records

    async def extract_records_async(self, limit: Optional[int] = None) -> List[PestMonitoringRecord]:
        """
        Asynchronous orchestrator for PowerBI extraction.
        """
        payloads = await self._intercept_querydata_responses()
        if not payloads:
            return []
        return self._decode_powerbi_rows(payloads, limit=limit)

    def extract_records(self, limit: Optional[int] = None) -> List[PestMonitoringRecord]:
        """
        Synchronous wrapper using asyncio loop.
        """
        return asyncio.run(self.extract_records_async(limit=limit))


def extract_powerbi_data(limit: Optional[int] = None) -> List[PestMonitoringRecord]:
    """
    Functional entry point for PowerBI extractor.
    """
    extractor = PowerBiMaizExtractor()
    return extractor.extract_records(limit=limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    recs = extract_powerbi_data()
    print(f"\nExtracted {len(recs)} PowerBI records. Sample:")
    for r in recs[:5]:
        print(f"Date={r.occurrence_date.date()} Locality={r.locality} Prov={r.province} Lat={r.latitude:.4f} Lon={r.longitude:.4f} Severity={r.severity_level}")
