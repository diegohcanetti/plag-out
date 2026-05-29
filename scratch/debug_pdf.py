import logging
import sys
from transformers.aappce_pdf import parse_aappce_pdf
import transformers.aappce_pdf as aappce_pdf

# Monkey-patch the loop inside parse_grid_page to print what's going on
original_parse_grid_page = aappce_pdf.parse_grid_page

def debug_parse_grid_page(page, col_coords, report_date, geocoder, records):
    print(f"Col Coords: {col_coords}")
    original_parse_grid_page(page, col_coords, report_date, geocoder, records)
    # The records list is modified in place
    
aappce_pdf.parse_grid_page = debug_parse_grid_page

logging.basicConfig(level=logging.WARNING, stream=sys.stdout)
records = parse_aappce_pdf('data/aappce_pdfs/Informe-11-Red-MIP-AAPPCE.pdf')
print(f"Extracted {len(records)} records")
