import os
import logging
import asyncio
from typing import Optional
from urllib.parse import urljoin, urlparse
import time

import aiohttp
import requests
from bs4 import BeautifulSoup
import trafilatura

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self):
        self.scrape_do_token = os.getenv("SCRAPE_DO_TOKEN", "feb4f86327e14e9d9f92036d4167ac51b4e35ccd880")
        self.domain_last_request = {}
        self.min_delay_per_domain = 1.0  # 1 second between requests to same domain
        
        # Scrape.do base URL
        self.scrape_do_url = "http://api.scrape.do"
    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            response = requests.get(robots_url, timeout=5)
            if response.status_code == 200:
                content = response.text.lower()
                path = parsed_url.path or "/"
                
                # Check for specific disallow rules that match our path
                lines = content.split('\n')
                user_agent_applies = False
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('user-agent:'):
                        agent = line.split(':', 1)[1].strip()
                        user_agent_applies = agent == '*' or 'scraperapi' in agent
                    elif user_agent_applies and line.startswith('disallow:'):
                        disallow_path = line.split(':', 1)[1].strip()
                        # Only block if there's an exact "disallow: /" or our path matches
                        if disallow_path == "/" or (disallow_path and path.startswith(disallow_path)):
                            logger.warning(f"Robots.txt disallows path {path} for {url}")
                            return False
            return True
        except Exception as e:
            logger.debug(f"Could not check robots.txt for {url}: {e}")
            return True  # Allow if can't check

    async def _rate_limit_domain(self, url: str):
        """Apply rate limiting per domain"""
        domain = urlparse(url).netloc
        current_time = time.time()
        
        if domain in self.domain_last_request:
            time_since_last = current_time - self.domain_last_request[domain]
            if time_since_last < self.min_delay_per_domain:
                await asyncio.sleep(self.min_delay_per_domain - time_since_last)
        
        self.domain_last_request[domain] = time.time()

    def scrapedo_fetch(self, url: str) -> Optional[str]:
        """
        Fetch page content using scrape.do (synchronous, requests-based)
        """
        try:
            # Rate limiting
            self._rate_limit_domain_sync(url)

            logger.info(f"Fetching page with scrape.do: {url}")
            scrape_url = f"{self.scrape_do_url}?token={self.scrape_do_token}&url={url}"
            response = requests.get(scrape_url, timeout=30)
            if response.status_code == 200:
                html_content = response.text
                # Extract clean text using trafilatura
                clean_text = trafilatura.extract(html_content)
                if clean_text:
                    logger.info(f"Successfully extracted {len(clean_text)} characters from {url}")
                    return clean_text
                else:
                    # Fallback to BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    for script in soup(["script", "style"]):
                        script.decompose()
                    text = soup.get_text()
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    logger.info(f"Fallback extraction: {len(text)} characters from {url}")
                    return text
            else:
                logger.error(f"scrape.do returned status {response.status_code} for {url}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch {url} with scrape.do: {e}")
            return None

    def _rate_limit_domain_sync(self, url: str):
        """Synchronous rate limiting per domain for requests-based fetch."""
        domain = urlparse(url).netloc
        current_time = time.time()
        if domain in self.domain_last_request:
            time_since_last = current_time - self.domain_last_request[domain]
            if time_since_last < self.min_delay_per_domain:
                time.sleep(self.min_delay_per_domain - time_since_last)
        self.domain_last_request[domain] = time.time()

    # Optionally, keep the old async method for compatibility, but point it to the new sync method
    async def scraperapi_fetch(self, url: str) -> Optional[str]:
        """Alias for scrapedo_fetch for compatibility (runs in thread executor)."""
        import concurrent.futures
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.scrapedo_fetch, url)

    async def selenium_fetch(self, url: str) -> Optional[str]:
        """Alias for scraperapi_fetch (now using scrape.do) for compatibility."""
        return await self.scraperapi_fetch(url)

    async def get_page_title(self, url: str) -> str:
        """Extract page title using ScraperAPI"""
        try:
            # ScraperAPI parameters for title extraction
            params = {
                'api_key': self.scraperapi_key,
                'url': url,
                'country_code': 'us'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.scraperapi_url, params=params, timeout=15) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        soup = BeautifulSoup(html_content, 'html.parser')
                        title_tag = soup.find('title')
                        return title_tag.text.strip() if title_tag else url
                    else:
                        return url
        except Exception as e:
            logger.error(f"Failed to get title for {url}: {e}")
            return url
    
    async def cleanup(self):
        """Clean up resources - no longer needed with ScraperAPI"""
        logger.info("ScraperAPI service cleanup - no resources to clean")
