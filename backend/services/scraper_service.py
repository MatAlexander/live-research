import os
import logging
import asyncio
from typing import Optional
from urllib.parse import urljoin, urlparse
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import trafilatura
import requests

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self):
        self.driver = None
        self.domain_last_request = {}
        self.min_delay_per_domain = 1.0  # 1 second between requests to same domain
        
    async def _init_driver(self):
        """Initialize Chrome driver if not already done"""
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("Chrome driver initialized")

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            response = requests.get(robots_url, timeout=5)
            if response.status_code == 200:
                # Simple check - in production you'd want proper robots.txt parsing
                content = response.text.lower()
                if "user-agent: *" in content and "disallow: /" in content:
                    logger.warning(f"Robots.txt disallows scraping for {url}")
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

    async def selenium_fetch(self, url: str) -> Optional[str]:
        """
        Fetch page content using Selenium with headless Chrome
        """
        try:
            # Check robots.txt
            if not await self._check_robots_txt(url):
                return None
            
            # Rate limiting
            await self._rate_limit_domain(url)
            
            # Initialize driver if needed
            await self._init_driver()
            
            logger.info(f"Fetching page: {url}")
            
            # Navigate to page
            self.driver.get(url)
            
            # Wait for network idle (simplified - wait for page load)
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Additional wait for dynamic content
            await asyncio.sleep(2)
            
            # Get page source
            html_content = self.driver.page_source
            
            # Extract clean text using trafilatura
            clean_text = trafilatura.extract(html_content)
            
            if clean_text:
                logger.info(f"Successfully extracted {len(clean_text)} characters from {url}")
                return clean_text
            else:
                # Fallback to BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                logger.info(f"Fallback extraction: {len(text)} characters from {url}")
                return text
                
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
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
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Chrome driver cleaned up")
