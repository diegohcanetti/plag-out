"""
Unit Tests for MAIZAR PDF Parser
"""

import os
from datetime import datetime
import pytest
from transformers.maizar_pdf import parse_maizar_pdf


def test_parse_maizar_pdf_real():
    """
    Verifies the PDF parser extracts structured records from the actual downloaded PDF.
    """
    pdf_path = "42_report.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("Test PDF not present. Skipping real integration parsing test.")
        
    report_date = datetime(2026, 5, 20)
    records = parse_maizar_pdf(pdf_path, report_date)
    
    assert len(records) > 0, "No records extracted from the PDF!"
    
    # Verify records have correct types and data
    for rec in records:
        assert rec.pest_type == "Dalbulus maidis"
        assert rec.occurrence_date == report_date
        assert rec.province in [
            "Santiago del Estero", "Santa Fe", "Entre Ríos", "Buenos Aires", 
            "La Pampa", "San Luis", "Jujuy", "Salta", "Tucumán", "Catamarca", 
            "Chaco", "Formosa", "Corrientes", "Córdoba", "Uruguay"
        ]
        assert rec.institution in ["CREA", "INTA", "AAPRESID", "AAPPCE", "AGTSA", "UNNOBA"]
        assert rec.latitude == 0.0  # Before geocoding
        assert rec.longitude == 0.0  # Before geocoding
        
    print(f"Verified {len(records)} parsed records successfully!")
