import logging
from transformers.aappce_pdf import parse_aappce_pdf

logging.basicConfig(level=logging.INFO)

recs = parse_aappce_pdf("data/aappce_pdfs/Informe-10-Red-MIP-AAPPCE.pdf")
print(f"\nExtracted {len(recs)} records. Samples:")
for r in recs[:10]:
    print(f"Pest={r.pest_type} Locality={r.locality} Province={r.province} Severity={r.severity_level} Count={r.adults_count}")
