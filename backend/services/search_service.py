import os
import time
import logging
from typing import List
from googlesearch import search
import asyncio

from models.schemas import SearchResult

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        self.delay_sec = float(os.getenv("GOOGLE_DELAY_SEC", "2.0"))
        self.last_search_time = 0
        
    async def google_search(self, query: str, k: int = 10) -> List[SearchResult]:
        """
        Perform Google search with rate limiting
        """
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_search_time
        if time_since_last < self.delay_sec:
            await asyncio.sleep(self.delay_sec - time_since_last)
        
        try:
            logger.info(f"Performing Google search for: {query}")
            
            # Use googlesearch library
            search_results = []
            urls = search(query, num_results=k, lang="en")
            
            for i, url in enumerate(urls):
                if i >= k:
                    break
                    
                search_results.append(SearchResult(
                    url=url,
                    title=f"Search Result {i+1}",  # Will be updated when scraping
                    snippet=""  # Will be updated when scraping
                ))
                
            self.last_search_time = time.time()
            logger.info(f"Found {len(search_results)} search results")
            return search_results
            
        except Exception as e:
            logger.error(f"Google search failed: {e}")
            # Fallback to empty results
            return []
