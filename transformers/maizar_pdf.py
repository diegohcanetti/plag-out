"""
MAIZAR PDF Report Transformer

This module uses `pdfplumber` to extract and normalize tabular monitoring data
from the highlightable MAIZAR PDF reports. It converts the raw text representation
into a list of validated `PestMonitoringRecord` models.
"""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pdfplumber
from models.schemas import PestMonitoringRecord

logger = logging.getLogger(__name__)

# List of known provinces to ensure accurate spatial parsing
PROVINCES = [
    "Santiago del Estero", "Santa Fe", "Entre Ríos", "Buenos Aires", 
    "La Pampa", "San Luis", "Jujuy", "Salta", "Tucumán", "Catamarca", 
    "Chaco", "Formosa", "Corrientes", "Córdoba", "Uruguay"
]

# Known institutions involved in the monitoring
INSTITUTIONS = ["CREA", "INTA", "AAPRESID", "AAPPCE", "AGTSA", "UNNOBA"]


def determine_severity_level(count: Optional[int]) -> str:
    """
    Categorizes the insect density based on standard Plag-out thresholds.
    """
    if count is None:
        return "Unknown"
    if count == 0:
        return "Zero"
    elif 1 <= count <= 4:
        return "Low"
    elif 5 <= count <= 20:
        return "Medium"
    elif 21 <= count <= 100:
        return "High"
    else:  # > 100
        return "Explosive"


def clean_int_count(val: str) -> Optional[int]:
    """
    Cleans and parses the count string into an integer.
    Returns None for missing/lost data.
    """
    val_clean = val.strip().lower()
    if val_clean in ["sin datos", "perdida", "sin_datos", "sin-datos"]:
        return None
    try:
        # Strip commas or dots if any (e.g. 1.200 -> 1200)
        numeric_val = re.sub(r"[^\d]", "", val_clean)
        return int(numeric_val) if numeric_val else None
    except Exception:
        return None


def parse_line(line: str) -> Optional[Dict]:
    """
    Parses a single line of text from a MAIZAR report using right-to-left tokenization.
    """
    parts = line.strip().split()
    if not parts or not parts[0].isdigit() or len(parts) < 4:
        return None
        
    loc_id = parts[0]
    inst = parts[1]
    if inst not in INSTITUTIONS:
        return None
        
    # Match the province from the rest of the string
    rest_str = " ".join(parts[2:])
    province = None
    for p in PROVINCES:
        if rest_str.startswith(p):
            province = p
            rest_str = rest_str[len(p):].strip()
            break
            
    if not province:
        return None
        
    # Extract readings from the right side of the remaining string
    words = rest_str.split()
    readings = []
    
    i = len(words) - 1
    while i >= 0 and len(readings) < 3:
        word = words[i]
        if word.isdigit() or word.lower() == "perdida":
            readings.append(word)
            i -= 1
        elif i > 0 and words[i-1].lower() == "sin" and word.lower() == "datos":
            readings.append("sin datos")
            i -= 2
        else:
            break
            
    locality = " ".join(words[:i+1])
    readings.reverse()
    
    if not readings:
        return None
        
    return {
        "id": loc_id,
        "inst": inst,
        "prov": province,
        "loc": locality,
        "readings": readings
    }


def parse_maizar_pdf(
    pdf_path: str,
    report_date: datetime,
) -> List[PestMonitoringRecord]:
    """
    Parses a MAIZAR PDF report and extracts the latest reading for each locality.
    
    Args:
        pdf_path: Absolute path to the downloaded PDF file.
        report_date: The date corresponding to the latest reading.
        
    Returns:
        List[PestMonitoringRecord]: List of validated Pydantic models.
    """
    records = []
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file does not exist: {pdf_path}")
        return records

    # Keep track of parsed IDs to prevent duplication within the same report
    parsed_ids = set()

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
                
            for line in text.split("\n"):
                p = parse_line(line)
                if p:
                    # Prevent duplicate rows on overlapping pages
                    unique_key = (p["id"], p["prov"], p["loc"])
                    if unique_key in parsed_ids:
                        continue
                    parsed_ids.add(unique_key)
                    
                    # Extract the latest reading (last element)
                    latest_reading_str = p["readings"][-1]
                    count = clean_int_count(latest_reading_str)
                    severity = determine_severity_level(count)
                    
                    # Hardcoded spatial coords mapping since MAIZAR reports don't contain absolute coordinates inline,
                    # but we geocode them using local coordinates databases or geocoding APIs.
                    # We will implement geocoding fallback in spatial.py. For now, we stub coords as (0.0, 0.0)
                    # or look up from a pre-defined set of coordinates.
                    latitude, longitude = 0.0, 0.0
                    
                    record = PestMonitoringRecord(
                        occurrence_date=report_date,
                        pest_type="Dalbulus maidis",
                        severity_level=severity,
                        latitude=latitude,
                        longitude=longitude,
                        institution=p["inst"],
                        province=p["prov"],
                        locality=p["loc"],
                        adults_count=count,
                        infection_percent=None  # Can be populated if infection data is found
                    )
                    records.append(record)
                    
    logger.info(f"Extracted {len(records)} records from {pdf_path}")
    return records
