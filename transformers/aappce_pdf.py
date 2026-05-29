"""
AAPPCE PDF Report Transformer

This module uses `pdfplumber` to extract and normalize categorical monitoring data
from the AAPPCE monthly PDF reports. It converts the visual risk matrix circles (curves)
into a list of validated `PestMonitoringRecord` models.
"""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pdfplumber

from models.schemas import PestMonitoringRecord
from transformers.spatial import SpatialGeocoder

logger = logging.getLogger(__name__)

# Spanish months mapping to numbers
MONTHS_MAP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

# Hub mappings for geocoding the 12 Nodos
NODE_HUBS = {
    1: {"locality": "Las Lajitas", "province": "Salta"},
    2: {"locality": "Bandera", "province": "Santiago del Estero"},
    3: {"locality": "Gálvez", "province": "Santa Fe"},
    4: {"locality": "Jesus Maria", "province": "Córdoba"},
    5: {"locality": "San Francisco", "province": "Córdoba"},
    6: {"locality": "Paraná", "province": "Entre Ríos"},
    7: {"locality": "Cañada de Gómez", "province": "Santa Fe"},
    8: {"locality": "Venado Tuerto", "province": "Santa Fe"},
    9: {"locality": "Pergamino", "province": "Buenos Aires"},
    10: {"locality": "Pehuajó", "province": "Buenos Aires"},
    11: {"locality": "Bahía Blanca", "province": "Buenos Aires"},
    12: {"locality": "Tres Arroyos", "province": "Buenos Aires"}
}

# Pest name patterns to dynamically resolve column coordinates in PDF pages and parse text rows
PEST_PATTERNS = {
    "Dalbulus maidis": ["dalbulus", "sulublad", "maidis", "sidiam", "chicharrita", "atirrahcihc"],
    "Spodoptera frugiperda": ["spodoptera frugiperda", "aretpodos", "frugiperda", "adrepigurf", "cogollero", "orellogoc"],
    "Helicoverpa gelotopoeon": ["gelotopoeon", "noeopotoleg", "bolillera", "arellilob"],
    "Faronta albilinea": ["faronta", "atnoraf", "albilinea", "aenilibla", "desgranadora", "arodanargsed"],
    "Pseudaletia adultera": ["pseudaletia", "aiteladuesp", "adultera", "aretluda", "militar"],
    "Diatraea saccharalis": ["diatraea", "aeartaid", "saccharalis", "silarahccas", "barrenador", "rodanerrab"],
    "Rachiplusia nu": ["rachiplusia", "aisulpihcar", "medidora", "arodidem"],
    "Chrysodeixis includens": ["chrysodeixis", "includens", "falsa medidora", "arodidem aslaf"],
    "Helicoverpa zea": ["helicoverpa zea", "oruga de la espiga", "isoca de la espiga", "espiga"]
}

# Standard defaults for column x coordinates if headers are not resolved
DEFAULT_PAGE5_COLS = {
    "Dalbulus maidis": 159.0,
    "Helicoverpa gelotopoeon": 235.0,
    "Faronta albilinea": 311.0,
    "Spodoptera frugiperda": 333.0,
    "Pseudaletia adultera": 360.0,
    "Diatraea saccharalis": 384.0
}

DEFAULT_PAGE6_COLS = {
    "Rachiplusia nu": 114.0
}

# Grid y0 coordinates correspond to nodes 1 to 12 (top-to-bottom)
GRID_Y0S = [327.5, 303.4, 279.4, 255.4, 231.4, 207.3, 183.3, 159.2, 135.2, 111.2, 87.1, 63.1]


def extract_report_date(pdf) -> datetime:
    """
    Attempts to extract the monthly report date (Month Year) from the first few pages.
    """
    for page in pdf.pages[:3]:
        text = page.extract_text()
        if not text:
            continue
        for line in text.split("\n"):
            for m_name, m_num in MONTHS_MAP.items():
                if m_name in line.lower():
                    match = re.search(r"\b(20\d{2})\b", line)
                    if match:
                        year = int(match.group(1))
                        # Default to the middle of the month: 15th
                        return datetime(year, m_num, 15)
    
    # Fallback to checking Page 5 (index 4)
    if len(pdf.pages) >= 5:
        text = pdf.pages[4].extract_text()
        if text:
            for line in text.split("\n"):
                for m_name, m_num in MONTHS_MAP.items():
                    if m_name in line.lower():
                        match = re.search(r"\b(20\d{2})\b", line)
                        if match:
                            year = int(match.group(1))
                            return datetime(year, m_num, 15)
                            
    return datetime.now()


def resolve_columns(page, pest_mapping) -> Dict[str, float]:
    """
    Dynamically maps pest names to their x-coordinates based on word bounding boxes on the page.
    """
    col_coords = {}
    try:
        words = page.extract_words()
        for word in words:
            text_lower = word["text"].lower()
            for pest, patterns in pest_mapping.items():
                if pest in col_coords:
                    continue
                for pat in patterns:
                    if pat in text_lower:
                        cx = (word["x0"] + word["x1"]) / 2.0
                        col_coords[pest] = cx
                        logger.debug(f"Resolved column for '{pest}' at x={cx:.1f} (matched pattern '{pat}' in '{word['text']}')")
                        break
    except Exception as e:
        logger.warning(f"Error during column coordinate resolution: {e}")
    return col_coords


def map_color_to_severity(color: Tuple[float, ...]) -> Tuple[str, int]:
    """
    Maps visual color tuples of grid circle shapes to Plag-out severity level and adults_count.
    Green -> Low, Yellow/Orange -> Medium, Red -> High.
    """
    if len(color) == 4:
        c, m, y, k = color
        r = (1.0 - c) * (1.0 - k)
        g = (1.0 - m) * (1.0 - k)
        b = (1.0 - y) * (1.0 - k)
    elif len(color) == 3:
        r, g, b = color
    elif len(color) == 1:
        r = g = b = color[0]
    else:
        r, g, b = 1.0, 1.0, 1.0

    # Green is usually (0.0784, 0.698, 0.3333) or similar
    if g > 0.55 and r < 0.4:
        return "Low", 2
    # Red is usually (0.8824, 0.1765, 0.2353) or similar
    elif r > 0.8 and g < 0.4:
        return "High", 50
    # Yellow/Orange is usually (1.0, 0.5882, 0.0) or (1.0, 0.8627, 0.1373)
    elif r > 0.8 and g > 0.5:
        return "Medium", 12
    # Fallback to Medium if unknown colorful circle
    return "Medium", 12


def parse_aappce_pdf(pdf_path: str, report_date: Optional[datetime] = None) -> List[PestMonitoringRecord]:
    """
    Parses an AAPPCE PDF report. Automatically detects if the report is V1 (Matrix)
    or V2 (Per-Region Text List) and extracts biological records.
    """
    records = []
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file does not exist: {pdf_path}")
        return records

    geocoder = SpatialGeocoder()

    with pdfplumber.open(pdf_path) as pdf:
        if not report_date:
            report_date = extract_report_date(pdf)
            logger.info(f"Automatically extracted report date: {report_date.strftime('%Y-%m-%d')}")

        # Detect if it's V2 (text-based list per region)
        is_v2 = False
        ref_page_idx = -1
        for idx in range(3, min(len(pdf.pages), 8)):
            text = pdf.pages[idx].extract_text()
            if text and ("REFERENCIAS" in text.upper() or "RIESGO BAJO" in text.upper() or ("REFE" in text.upper() and "REN" in text.upper() and "CIAS" in text.upper())):
                is_v2 = True
                ref_page_idx = idx
                break

        if is_v2:
            logger.info(f"Detected AAPPCE V2 format in {pdf_path}. Parsing text-based nodes...")
            # Parse consecutive pages starting from ref_page_idx + 1 representing the 12 Nodos
            for node_id in range(1, 13):
                page_idx = ref_page_idx + node_id
                if page_idx >= len(pdf.pages):
                    break
                page = pdf.pages[page_idx]
                text = page.extract_text()
                if not text:
                    continue

                hub = NODE_HUBS.get(node_id)
                if not hub:
                    continue

                lat, lon = geocoder.geocode(hub["locality"], hub["province"])

                lines = text.split("\n")
                for line in lines:
                    line_lower = line.lower()
                    # Stop parsing if we reach the footer/comments section
                    if any(k in line_lower for k in ["¿a qué prestar", "fecha", "coordina", "observaciones generales", "informe #", "auspician"]):
                        break

                    for pest, patterns in PEST_PATTERNS.items():
                        matched = False
                        for pat in patterns:
                            if pat in line_lower:
                                # Found the pest pattern! Now let's extract the severity (B, M, A)
                                idx_pat = line_lower.find(pat)
                                sub = line[idx_pat + len(pat):].strip()

                                # Match crops followed by B, M, or A
                                match = re.search(r'\b(?:[A-Z]{2,4}\s+)*\b([BMA])\b', sub)
                                if not match:
                                    # Loose search for the first B, M, or A in the rest of the line
                                    match = re.search(r'\b([BMA])\b', sub)

                                if match:
                                    severity_code = match.group(1)
                                    if severity_code == "B":
                                        severity = "Low"
                                        count = 2
                                    elif severity_code == "A":
                                        severity = "High"
                                        count = 50
                                    else:
                                        severity = "Medium"
                                        count = 12

                                    records.append(PestMonitoringRecord(
                                        occurrence_date=report_date,
                                        pest_type=pest,
                                        severity_level=severity,
                                        latitude=lat,
                                        longitude=lon,
                                        institution="AAPPCE (Red MIP)",
                                        province=hub["province"],
                                        locality=hub["locality"],
                                        adults_count=count,
                                        infection_percent=None
                                    ))
                                    matched = True
                                    break
                        if matched:
                            break
        else:
            # V1 shape-based matrix layout
            # Page 5 (Index 4) - Insectos y Ácaros Parte 1
            if len(pdf.pages) >= 5:
                logger.info(f"Parsing insects on Page 5 of {pdf_path} (V1 format)...")
                page5 = pdf.pages[4]
                
                # Resolve dynamic columns
                col_coords = resolve_columns(page5, PEST_PATTERNS)
                # Apply defaults if not resolved
                for pest, default_x in DEFAULT_PAGE5_COLS.items():
                    if pest not in col_coords:
                        col_coords[pest] = default_x
                        
                parse_grid_page(page5, col_coords, report_date, geocoder, records)

            # Page 6 (Index 5) - Insectos y Ácaros Parte 2
            if len(pdf.pages) >= 6:
                logger.info(f"Parsing insects on Page 6 of {pdf_path} (V1 format)...")
                page6 = pdf.pages[5]
                
                # Resolve dynamic columns
                col_coords = resolve_columns(page6, PEST_PATTERNS)
                for pest, default_x in DEFAULT_PAGE6_COLS.items():
                    if pest not in col_coords:
                        col_coords[pest] = default_x
                        
                parse_grid_page(page6, col_coords, report_date, geocoder, records)

    logger.info(f"Successfully extracted {len(records)} records from AAPPCE PDF: {pdf_path}")
    return records


def parse_grid_page(
    page, 
    col_coords: Dict[str, float], 
    report_date: datetime, 
    geocoder: SpatialGeocoder, 
    records: List[PestMonitoringRecord]
) -> None:
    """
    Helper function to process the circle grid on a single page.
    """
    # Group and filter curves that represent grid cells (circles of size 15.23)
    grid_shapes = []
    for c in page.curves:
        color = c.get("non_stroking_color")
        if not color or color in [(0.9961, 0.9961, 0.9961), (1.0, 1.0, 1.0), (0.9373, 0.9725, 0.9804)]:
            continue
        width = c["x1"] - c["x0"]
        height = c["y1"] - c["y0"]
        # Check size matching circle 15.23 (with some tolerance)
        if abs(width - 15.23) < 3.0 and abs(height - 15.23) < 3.0:
            grid_shapes.append(c)

    logger.info(f"Found {len(grid_shapes)} visual risk circle shapes on page.")

    # Dynamically align the row coordinates in case the PDF layout shifted
    if grid_shapes:
        y0s = sorted({s["y0"] for s in grid_shapes}, reverse=True)
        clusters = []
        for y in y0s:
            if not clusters or abs(clusters[-1] - y) > 5.0:
                clusters.append(y)
                
        best_offset = 0.0
        min_error = float('inf')
        for offset in range(-150, 150, 1):
            error = sum(min(abs(target_y + offset - cy) for target_y in GRID_Y0S) for cy in clusters)
            if error < min_error:
                min_error = error
                best_offset = offset
                
        adjusted_y0s = [y + best_offset for y in GRID_Y0S]
    else:
        adjusted_y0s = GRID_Y0S

    for s in grid_shapes:
        color = s["non_stroking_color"]
        cx = (s["x0"] + s["x1"]) / 2.0
        cy0 = s["y0"]

        # Resolve Node Row dynamically
        matched_node_id = None
        for idx, target_y in enumerate(adjusted_y0s):
            if abs(target_y - cy0) < 6.0:
                matched_node_id = idx + 1
                break

        if not matched_node_id or matched_node_id not in NODE_HUBS:
            continue

        hub = NODE_HUBS[matched_node_id]

        # Match column x coordinate to a pest type
        matched_pest = None
        min_distance = 15.0
        for pest, col_x in col_coords.items():
            dist = abs(col_x - cx)
            if dist < min_distance:
                min_distance = dist
                matched_pest = pest

        if not matched_pest:
            continue

        severity, count = map_color_to_severity(color)
        
        # Geocode representative hub
        lat, lon = geocoder.geocode(hub["locality"], hub["province"])

        record = PestMonitoringRecord(
            occurrence_date=report_date,
            pest_type=matched_pest,
            severity_level=severity,
            latitude=lat,
            longitude=lon,
            institution="AAPPCE (Red MIP)",
            province=hub["province"],
            locality=hub["locality"],
            adults_count=count,
            infection_percent=None
        )
        records.append(record)
