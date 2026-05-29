"""
AAPPCE Periodic Reports Extractor

This module crawls the official AAPPCE 'Informes Red MIP' webpage,
discovers monthly PDF reports, downloads them, and orchestrates
the extraction of agricultural pest monitoring records.
"""

import os
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
import urllib3

from models.schemas import PestMonitoringRecord
from transformers.aappce_pdf import parse_aappce_pdf
from loaders.db import quarantine_failed_file

logger = logging.getLogger(__name__)

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def extract_aappce_data(limit_reports: Optional[int] = None) -> List[PestMonitoringRecord]:
    """
    Crawls AAPPCE for PDF links, downloads the reports, and parses them.
    
    Args:
        limit_reports: Maximum number of PDF reports to process.
        
    Returns:
        List[PestMonitoringRecord]: Extracted agricultural pest occurrence records.
    """
    url = "https://aappce.org/informes_redmip/"
    logger.info(f"Crawling AAPPCE reports page: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    pdf_urls = []
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=20)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.find_all('a')
            for l in links:
                href = l.get('href')
                if href and href.lower().endswith('.pdf'):
                    # Filter to keep only Red MIP / Monitoreo reports
                    href_lower = href.lower()
                    if "mip" in href_lower or "monitoreo" in href_lower:
                        if href not in pdf_urls:
                            pdf_urls.append(href)
        else:
            logger.error(f"Failed to fetch AAPPCE reports page. Status: {res.status_code}")
    except Exception as e:
        logger.error(f"Failed to crawl AAPPCE page: {e}")
        
    if not pdf_urls:
        logger.warning("No AAPPCE Red MIP PDF reports discovered.")
        return []
        
    # Apply limit
    if limit_reports:
        logger.info(f"Limiting processing to first {limit_reports} discovered AAPPCE reports.")
        pdf_urls = pdf_urls[:limit_reports]
        
    logger.info(f"Discovered {len(pdf_urls)} unique AAPPCE PDF reports to parse.")
    
    records = []
    os.makedirs("data/aappce_pdfs", exist_ok=True)
    
    for idx, pdf_url in enumerate(pdf_urls):
        filename = pdf_url.split("/")[-1]
        local_path = os.path.join("data", "aappce_pdfs", filename)
        
        # Download PDF if it doesn't already exist
        if not os.path.exists(local_path):
            logger.info(f"[{idx+1}/{len(pdf_urls)}] Downloading {pdf_url} to {local_path}...")
            try:
                r = requests.get(pdf_url, headers=headers, verify=False, timeout=30)
                with open(local_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                logger.error(f"Failed to download AAPPCE PDF from {pdf_url}: {e}")
                continue
        else:
            logger.info(f"[{idx+1}/{len(pdf_urls)}] Using cached PDF: {local_path}")
            
        # Parse PDF
        try:
            parsed_recs = parse_aappce_pdf(local_path)
            records.extend(parsed_recs)
        except Exception as e:
            logger.error(f"Failed to parse AAPPCE PDF {local_path}: {e}")
            quarantine_failed_file(local_path, str(e))
            
    logger.info(f"End-to-End AAPPCE extraction complete. Extracted {len(records)} total records.")
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    recs = extract_aappce_data(limit_reports=1)
    print(f"\nExtracted {len(recs)} sample records from AAPPCE PDF:")
    for r in recs[:10]:
        print(f"  Pest={r.pest_type} Date={r.occurrence_date.date()} Locality={r.locality} Prov={r.province} Severity={r.severity_level} Count={r.adults_count}")
