import json
from typing import List, Dict, Any, Optional
from loguru import logger

from ..llm.claude_client import ClaudeClient
from ..llm.prompts import SYSTEM_PROMPT_FORECASTER, FORECAST_SCHEMA
from ..data_store.repository import DatabaseRepository
from ..data_store.models import Forecast, MarketCandidate
from ..config import get_config


class ForecasterAgent:
    def __init__(
        self,
        llm_client: ClaudeClient,
        repository: DatabaseRepository
    ):
        self.llm = llm_client
        self.repo = repository
        self.config = get_config()
    
    def run_step(
        self,
        candidate: MarketCandidate,
        market_info: Dict,
        research_data: Any
    ) -> Forecast:
        logger.info(f"ForecasterAgent: Forecasting for market {candidate.market_id}")
        
        cached = self.repo.get_cached_forecast(candidate.market_id)
        if cached:
            logger.info(f"ForecasterAgent: Using cached forecast for {candidate.market_id}")
            return Forecast(**cached)
        
        forecast = self._generate_forecast(candidate, market_info, research_data)
        
        self.repo.cache_forecast(candidate.market_id, forecast.model_dump(), forecast.confidence)
        
        return forecast
    
    def _generate_forecast(
        self,
        candidate: MarketCandidate,
        market_info: Dict,
        research_data: Dict
    ) -> Forecast:
        market_price = candidate.market_price
        
        context = f"""
MARKET INFORMATION:
Question: {candidate.title}
Category: {candidate.category}
Liquidity: ${candidate.liquidity:,.2f}
Volume 24h: ${candidate.volume_24h:,.2f}
Time to Resolve: {candidate.time_to_resolve}

CURRENT MARKET PRICES:
{json.dumps(market_price, indent=2)}

OUTCOMES:
{json.dumps(candidate.outcomes, indent=2)}

RESEARCH SUMMARY:
Key Facts: {json.dumps(research_data.get('key_facts', []), indent=2)}

Bull Case: {research_data.get('bull_case', 'N/A')}
Bear Case: {research_data.get('bear_case', 'N/A')}
Market Relevance: {research_data.get('market_relevance', 'MEDIUM')}
Research Confidence: {research_data.get('confidence', 'MEDIUM')}
"""

        user_message = f"""As a senior prediction market trader with 20+ years of experience, analyze this market and provide calibrated probability estimates.

{context}

Consider:
1. The current market prices reflect collective wisdom - are they reasonable?
2. Your research and any edge you can identify
3. Base rates and historical accuracy for similar markets
4. Time decay and resolution probability
5. Any information asymmetry or special knowledge

IMPORTANT:
- Probabilities must sum to 1.0 (or close to it)
- Be conservative and avoid overconfidence
- Consider both the YES and NO (or other) outcomes
- Note any significant mispricing vs your estimates

Return JSON with:
- outcomes: array of {{name, probability, confidence, notes}}
- summary: brief market analysis (2-3 sentences)
- market_sentiment: BULLISH/BEARISH/NEUTRAL
- key_factors: array of 3-5 most important factors
- confidence: overall confidence in this forecast (HIGH/MEDIUM/LOW)
"""

        response = self.llm.complete(
            system_prompt=SYSTEM_PROMPT_FORECASTER,
            user_message=user_message,
            json_output=True
        )
        
        parsed = self.llm.parse_json_response(response)
        if parsed:
            parsed["market_id"] = candidate.market_id
            return Forecast(**parsed)
        
        return self._default_forecast(candidate)
    
    def _default_forecast(self, candidate: MarketCandidate) -> Forecast:
        total_price = sum(candidate.market_price.values())
        outcomes = []
        
        for i, outcome in enumerate(candidate.outcomes):
            name = outcome.get("name", f"Outcome_{i}")
            price = candidate.market_price.get(name, 0.5)
            prob = price if price > 0 else 0.5
            
            outcomes.append({
                "name": name,
                "probability": prob,
                "confidence": "LOW",
                "notes": "Default forecast - LLM unavailable"
            })
        
        return Forecast(
            market_id=candidate.market_id,
            outcomes=outcomes,
            summary="Default forecast due to LLM error",
            market_sentiment="NEUTRAL",
            key_factors=["LLM unavailable"],
            confidence="LOW"
        )
    
    def compare_to_market(self, forecast: Forecast, candidate: MarketCandidate) -> List[Dict]:
        comparisons = []
        
        for outcome in forecast.outcomes:
            name = outcome["name"]
            your_prob = outcome["probability"]
            market_price = candidate.market_price.get(name, 0.5)
            implied_prob = market_price
            
            edge = your_prob - implied_prob
            
            comparisons.append({
                "outcome": name,
                "your_probability": your_prob,
                "market_price": market_price,
                "implied_probability": implied_prob,
                "edge": edge,
                "edge_pct": (edge / implied_prob * 100) if implied_prob > 0 else 0,
                "verdict": "BUY" if edge > 0.05 else ("SELL" if edge < -0.05 else "NO_EDGE")
            })
        
        return comparisons
