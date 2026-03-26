import json
from typing import List, Dict, Any, Optional
from loguru import logger

from ..llm.claude_client import ClaudeClient
from ..llm.prompts import SYSTEM_PROMPT_RESEARCH, RESEARCH_SCHEMA
from ..clients.web_search_client import WebSearchClient
from ..clients.polymarket_client import PolymarketClient
from ..data_store.repository import DatabaseRepository
from ..data_store.models import ResearchResult
from ..config import get_config


class ResearchAgent:
    def __init__(
        self,
        llm_client: ClaudeClient,
        web_client: WebSearchClient,
        polymarket_client: PolymarketClient,
        repository: DatabaseRepository
    ):
        self.llm = llm_client
        self.web = web_client
        self.polymarket = polymarket_client
        self.repo = repository
        self.config = get_config()
        self.max_articles = self.config.settings.research.max_articles
        self.max_tokens = self.config.settings.research.max_text_tokens_to_send
    
    def run_step(self, market_id: str, market_title: str) -> ResearchResult:
        logger.info(f"ResearchAgent: Researching market {market_id}: {market_title[:50]}...")
        
        cached = self.repo.get_cached_research(market_id)
        if cached:
            logger.info(f"ResearchAgent: Using cached research for {market_id}")
            return ResearchResult(**cached)
        
        market_info = self.polymarket.get_market_info(market_id)
        if not market_info:
            logger.warning(f"ResearchAgent: Could not fetch market info for {market_id}")
            return self._empty_result(market_id, market_title)
        
        query = self._build_search_query(market_title, market_info)
        
        news_results = self._fetch_news(query)
        
        research_data = self._compile_research(market_info, news_results)
        
        llm_summary = self._generate_llm_summary(market_info, research_data)
        
        result = ResearchResult(
            market_id=market_id,
            query=query,
            key_facts=research_data.get("key_facts", []),
            bull_case=llm_summary.get("bull_case", ""),
            bear_case=llm_summary.get("bear_case", ""),
            market_relevance=llm_summary.get("market_relevance", "MEDIUM"),
            confidence=llm_summary.get("confidence", "MEDIUM"),
            sources=[n["url"] for n in news_results[:3]]
        )
        
        self.repo.cache_research(market_id, query, result.model_dump())
        
        logger.info(f"ResearchAgent: Completed research for {market_id}")
        return result
    
    def _build_search_query(self, market_title: str, market_info: Dict) -> str:
        query = market_title
        
        category = market_info.get("category", "")
        if category:
            query = f"{category} {market_title}"
        
        return query[:200]
    
    def _fetch_news(self, query: str) -> List[Dict[str, Any]]:
        try:
            news = self.web.search_news(query, limit=self.max_articles)
            logger.info(f"ResearchAgent: Found {len(news)} news articles")
            return news
        except Exception as e:
            logger.warning(f"ResearchAgent: News search failed: {e}")
            return []
    
    def _compile_research(self, market_info: Dict, news_results: List[Dict]) -> Dict:
        key_facts = []
        
        key_facts.append(f"Market: {market_info.get('question', 'Unknown')}")
        
        outcomes = market_info.get("outcomes", [])
        if outcomes:
            key_facts.append(f"Outcomes: {', '.join(outcomes)}")
        
        prices = market_info.get("prices", {})
        if prices:
            price_str = ", ".join([f"{k}: ${v:.2f}" for k, v in prices.items()])
            key_facts.append(f"Current prices: {price_str}")
        
        liquidity = market_info.get("liquidity", 0)
        if liquidity:
            key_facts.append(f"Liquidity: ${liquidity:,.2f}")
        
        volume = market_info.get("volume_24h", 0)
        if volume:
            key_facts.append(f"24h Volume: ${volume:,.2f}")
        
        for news in news_results[:5]:
            title = news.get("title", "")
            snippet = news.get("snippet", "")
            if title:
                key_facts.append(f"NEWS: {title}")
        
        return {"key_facts": key_facts}
    
    def _generate_llm_summary(self, market_info: Dict, research_data: Dict) -> Dict:
        context = f"""
Market: {market_info.get('question', 'Unknown')}
Description: {market_info.get('description', 'N/A')}
Outcomes: {', '.join(market_info.get('outcomes', []))}
Prices: {market_info.get('prices', {})}
Liquidity: ${market_info.get('liquidity', 0):,.2f}

Key Facts & News:
{chr(10).join(research_data.get('key_facts', [])[:10])}
"""
        
        user_message = f"""Based on this market data and research, provide a brief bull case, bear case, and overall market relevance assessment.

{context}

Return JSON with:
- bull_case: Why the YES outcome might win (2-3 sentences)
- bear_case: Why the NO outcome might win (2-3 sentences)
- market_relevance: HIGH/MEDIUM/LOW based on news impact
- confidence: Your confidence in this assessment (HIGH/MEDIUM/LOW)

Be concise and focus on facts, not speculation."""

        response = self.llm.complete(
            system_prompt=SYSTEM_PROMPT_RESEARCH,
            user_message=user_message,
            json_output=True
        )
        
        parsed = self.llm.parse_json_response(response)
        if parsed:
            return parsed
        
        return {
            "bull_case": "Insufficient data for bull case",
            "bear_case": "Insufficient data for bear case",
            "market_relevance": "MEDIUM",
            "confidence": "LOW"
        }
    
    def _empty_result(self, market_id: str, market_title: str) -> ResearchResult:
        return ResearchResult(
            market_id=market_id,
            query=market_title,
            key_facts=[f"Could not fetch detailed research for {market_title}"],
            bull_case="Research unavailable",
            bear_case="Research unavailable",
            market_relevance="UNKNOWN",
            confidence="LOW",
            sources=[]
        )
