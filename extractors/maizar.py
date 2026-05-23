"""
MAIZAR Reports Extractor

This module handles scraping the MAIZAR website to discover all published reports
for the "Red Nacional de Monitoreo de Dalbulus maidis", extract their PDF links,
and download them locally.
"""

import os
import re
import logging
from typing import List, Dict, Optional
import urllib.parse
import requests
from bs4 import BeautifulSoup
import requests_cache

logger = logging.getLogger(__name__)

# Base URLs
BASE_URL = "https://www.maizar.org.ar"
SECCION_URL = f"{BASE_URL}/vertodas_area.php?id=39"

# Configure local request caching for web scraping
requests_cache.install_cache(
    ".maizar_scraper_cache",
    expire_after=86400 * 7  # Cache web page crawls for 7 days
)


def get_headers() -> Dict[str, str]:
    """
    Returns standard request headers to avoid user-agent blocks.
    """
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }


def extract_report_number(title: str) -> Optional[int]:
    """
    Extracts the report number from the report title using resilient regexes.
    
    Examples:
        - "42° Informe sobre Red..." -> 42
        - "38º Informe..." -> 38
        - "Red Nacional... INFORME N°5" -> 5
    """
    # Pattern 1: "42°", "42º", "42 " followed by "Informe"
    match1 = re.search(r"(\d+)(?:[°º°]?|\s+)(?:Informe|INFORME|informe)", title)
    if match1:
        return int(match1.group(1))
        
    # Pattern 2: "INFORME N°5" or "Informe N° 5"
    match2 = re.search(r"(?:Informe|INFORME|informe)\s*(?:N[°º]|\s+)\s*(\d+)", title)
    if match2:
        return int(match2.group(1))
        
    # Fallback to any standalone digit in the title if nothing else matches
    match3 = re.search(r"(\d+)", title)
    if match3:
        return int(match3.group(1))
        
    return None


def fetch_report_pages() -> List[Dict[str, str]]:
    """
    Scrapes the list page to find all individual report links and metadata.
    
    Returns:
        List[Dict[str, str]]: List of dictionaries containing "title", "url", "id", "report_num".
    """
    logger.info(f"Crawling MAIZAR index page: {SECCION_URL}")
    response = requests.get(SECCION_URL, headers=get_headers(), timeout=20)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    reports = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "vertext.php?id=" in href:
            title = a.get_text(strip=True)
            # Avoid duplicate links or links that don't look like monitoring reports
            if "monitoreo" in title.lower() or "dalbulus" in title.lower() or "informe" in title.lower():
                report_num = extract_report_number(title)
                reports.append({
                    "title": title,
                    "url": f"{BASE_URL}/{href}",
                    "id": href.split("id=")[1],
                    "report_num": report_num
                })
                
    # De-duplicate reports by URL
    seen = set()
    unique_reports = []
    for r in reports:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique_reports.append(r)
            
    logger.info(f"Found {len(unique_reports)} unique MAIZAR reports on index.")
    return unique_reports


def fetch_pdf_url_from_page(page_url: str) -> Optional[str]:
    """
    Scrapes an individual report page to extract the PDF file download link.
    """
    logger.debug(f"Fetching PDF link from report page: {page_url}")
    try:
        response = requests.get(page_url, headers=get_headers(), timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "documentos/" in href.lower() and href.lower().endswith(".pdf"):
                # URL encode the filename part of the URL because it may contain spaces/special characters
                parsed_url = urllib.parse.urlparse(href)
                # If it's a relative path, make it absolute
                if not parsed_url.scheme:
                    # e.g., documents/xxx.pdf or http://...
                    full_href = f"{BASE_URL}/{href.lstrip('/')}"
                else:
                    full_href = href
                    
                # Encode path to handle spaces
                url_parts = list(urllib.parse.urlparse(full_href))
                url_parts[2] = urllib.parse.quote(url_parts[2])
                final_url = urllib.parse.urlunparse(url_parts)
                return final_url
    except Exception as e:
        logger.error(f"Error extracting PDF URL from {page_url}: {e}")
        
    return None


def download_pdf(pdf_url: str, output_path: str) -> bool:
    """
    Downloads a PDF file from a URL to a local destination.
    Uses standard streaming to handle files safely.
    """
    if os.path.exists(output_path):
        logger.info(f"File already downloaded: {output_path}")
        return True
        
    logger.info(f"Downloading PDF from: {pdf_url}")
    try:
        response = requests.get(pdf_url, headers=get_headers(), stream=True, timeout=30)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info(f"Successfully downloaded to: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download PDF {pdf_url}: {e}")
        return False


def download_all_reports(output_dir: str = "data/maizar_pdfs") -> List[Dict]:
    """
    Orchestrates the entire discovery and download pipeline for all MAIZAR reports.
    
    Returns:
        List[Dict]: Metadata of all successfully downloaded reports.
    """
    reports = fetch_report_pages()
    downloaded_reports = []
    
    for r in reports:
        pdf_url = fetch_pdf_url_from_page(r["url"])
        if not pdf_url:
            logger.warning(f"Could not find PDF link for report: {r['title']}")
            continue
            
        r["pdf_url"] = pdf_url
        filename = f"report_{r['report_num'] or r['id']}.pdf"
        output_path = os.path.join(output_dir, filename)
        r["local_path"] = output_path
        
        success = download_pdf(pdf_url, output_path)
        if success:
            downloaded_reports.append(r)
            
    logger.info(f"Successfully downloaded {len(downloaded_reports)} / {len(reports)} reports.")
    return downloaded_reports


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Discovering MAIZAR reports...")
    pages = fetch_report_pages()
    print(f"Total reports listed: {len(pages)}")
    if pages:
        print(f"Latest report: {pages[0]}")
        pdf = fetch_pdf_url_from_page(pages[0]["url"])
        print(f"PDF Link: {pdf}")
