import time
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from loguru import logger

from ..config import get_config
from ..logging_utils import get_logger


class WebSearchClient:
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("web_search")
        self.timeout = self.config.settings.research.news_timeout_sec
        self._client = httpx.Client(timeout=float(self.timeout))
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self._client.close()
    
    def search_news(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        results = []
        
        try:
            google_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            response = self._client.get(
                "https://api.rss2json.com/v1/api.json",
                params={"rssurl": google_url, "count": limit}
            )
            
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", [])[:limit]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("description", "")[:500] if item.get("description") else "",
                        "published": item.get("pubDate", ""),
                        "source": item.get("author", "Google News")
                    })
        except Exception as e:
            self.logger.warning(f"Google News search failed: {e}")
        
        if len(results) < limit:
            try:
                crypto_url = f"https://cryptopanic.com/api/v1/posts/?auth_token=public&currency=USD&kind=news&q={query}&limit={limit}"
                response = self._client.get(crypto_url)
                
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("results", [])[:limit]:
                        results.append({
                            "title": item.get("title", {}).get("rendered", "")[:200],
                            "url": item.get("url", ""),
                            "snippet": item.get("domain", ""),
                            "published": item.get("published_at", ""),
                            "source": item.get("source", {}).get("title", "CryptoPanic")
                        })
            except Exception as e:
                self.logger.warning(f"CryptoPanic search failed: {e}")
        
        return results[:limit]
    
    def get_article_summary(self, url: str) -> Optional[str]:
        try:
            response = self._client.get(url)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                text = soup.get_text(separator=' ', strip=True)
                
                paragraphs = soup.find_all('p')
                content = ' '.join(p.get_text(strip=True) for p in paragraphs[:5])
                
                return content[:2000] if content else text[:2000]
        except Exception as e:
            self.logger.warning(f"Failed to fetch article: {e}")
        
        return None
    
    def search_polymarket_markets(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            url = f"https://gamma-api.polymarket.com/markets"
            params = {
                "search": query,
                "limit": limit,
                "closed": False
            }
            response = self._client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else data.get("markets", [])
        except Exception as e:
            self.logger.warning(f"Polymarket search failed: {e}")
        
        return []
    
    def get_trending_topics(self) -> List[str]:
        topics = []
        try:
            response = self._client.get(
                "https://gamma-api.polymarket.com/markets",
                params={"limit": 100, "closed": False}
            )
            
            if response.status_code == 200:
                data = response.json()
                markets = data if isinstance(data, list) else data.get("markets", [])
                
                categories = {}
                for market in markets:
                    cat = market.get("category", "Unknown")
                    categories[cat] = categories.get(cat, 0) + market.get("volume24hr", 0)
                
                topics = sorted(categories.keys(), key=lambda x: categories[x], reverse=True)[:10]
        except Exception as e:
            self.logger.warning(f"Failed to get trending topics: {e}")
        
        return topics


def get_web_search_client() -> WebSearchClient:
    return WebSearchClient()
