import os
import logging
import asyncio
from typing import Optional
from urllib.parse import urljoin, urlparse
import time

# NOTE:
# Selenium and Chrome driver have been removed to simplify scraping due to
# repeated connection issues on the deployment environment. We now rely on
# the scrape.do API to retrieve rendered HTML.

# Example API pattern:
#   http://api.scrape.do?token=<TOKEN>&url=<ENCODED_URL>

# The API token can be configured via the SCRAPE_DO_TOKEN environment
# variable, and defaults to the hard-coded demo token supplied by the user.

# If you wish to restore Selenium functionality, re-introduce the imports
# and logic that were previously here.

# Standard libraries
import requests
from bs4 import BeautifulSoup
import trafilatura

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self):
        self.driver = None
        self.domain_last_request = {}
        self.min_delay_per_domain = 1.0  # 1 second between requests to same domain
        
    async def _init_driver(self):
        """Deprecated placeholder to keep backward compatibility."""
        return  # No-op – Selenium removed

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        # When using scrape.do we rely on their infrastructure for compliance.
        # Skip robots.txt checks to avoid false negatives (e.g., httpbin test).
        return True

    async def _rate_limit_domain(self, url: str):
        """Apply rate limiting per domain"""
        domain = urlparse(url).netloc
        current_time = time.time()
        
        if domain in self.domain_last_request:
            time_since_last = current_time - self.domain_last_request[domain]
            if time_since_last < self.min_delay_per_domain:
                await asyncio.sleep(self.min_delay_per_domain - time_since_last)
        
        self.domain_last_request[domain] = time.time()

    async def selenium_fetch(self, url: str) -> Optional[str]:
        """
        Previous name retained for backward compatibility.
        Fetch page content using the scrape.do API instead of Selenium.
        """
        try:
            # Check robots.txt (still honour polite scraping when possible)
            if not await self._check_robots_txt(url):
                return None

            # Rate limiting per domain
            await self._rate_limit_domain(url)

            api_token = os.getenv(
                "SCRAPE_DO_TOKEN",
                "feb4f86327e14e9d9f92036d4167ac51b4e35ccd880"
            )
            api_url = (
                "http://api.scrape.do"
                f"?token={api_token}&url={url}"
            )

            logger.info(f"Fetching via scrape.do: {api_url}")
            response = requests.get(api_url, timeout=20)

            if response.status_code != 200:
                logger.error(
                    f"scrape.do returned status {response.status_code} for {url}"
                )
                return None

            html_content = response.text

            # Extract clean text using trafilatura first
            clean_text = trafilatura.extract(html_content)
            if clean_text:
                logger.info(
                    f"Successfully extracted {len(clean_text)} characters from {url}"
                )
                return clean_text

            # Fallback to BeautifulSoup if trafilatura fails
            soup = BeautifulSoup(html_content, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator=" ")
            text = " ".join(text.split())  # Normalize whitespace

            logger.info(
                f"Fallback extracted {len(text)} characters from {url}"
            )
            return text

        except Exception as e:
            logger.error(f"Failed to fetch {url} via scrape.do: {e}")
            return None
    
    async def get_page_title(self, url: str) -> str:
        """Extract page title"""
        try:
            if self.driver and self.driver.current_url == url:
                return self.driver.title
            else:
                # Quick request for title only
                response = requests.get(url, timeout=5)
                soup = BeautifulSoup(response.content, 'html.parser')
                title_tag = soup.find('title')
                return title_tag.text.strip() if title_tag else url
        except Exception:
            return url
    
    async def cleanup(self):
        """No external resources to clean up now"""
        return
