import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from ..llm.claude_client import ClaudeClient
from ..llm.prompts import SYSTEM_PROMPT_SCANNER, MARKET_SCAN_SCHEMA
from ..clients.polymarket_client import PolymarketClient
from ..data_store.models import MarketCandidate
from ..data_store.repository import DatabaseRepository
from ..config import get_config


class ScannerAgent:
    def __init__(
        self,
        llm_client: ClaudeClient,
        polymarket_client: PolymarketClient,
        repository: DatabaseRepository
    ):
        self.llm = llm_client
        self.polymarket = polymarket_client
        self.repo = repository
        self.config = get_config()
        self.max_markets = self.config.settings.global_settings.max_markets_per_cycle
        self.min_liquidity = self.config.settings.risk.min_liquidity_usd
    
    def run_step(self) -> List[MarketCandidate]:
        logger.info("ScannerAgent: Starting market scan...")
        
        try:
            markets = self.polymarket.list_markets(limit=100)
            logger.info(f"ScannerAgent: Fetched {len(markets)} markets from Polymarket")
        except Exception as e:
            logger.error(f"ScannerAgent: Failed to fetch markets: {e}")
            return []
        
        candidates = []
        for market_data in markets:
            try:
                market_id = market_data.get("id", "")
                if not market_id:
                    continue
                
                liquidity = self.polymarket.get_liquidity(market_id)
                volume_24h = market_data.get("volume24hr", 0) or 0
                
                if liquidity < self.min_liquidity and volume_24h < self.min_liquidity:
                    continue
                
                orderbook = self.polymarket.get_orderbook(market_id)
                outcomes = market_data.get("outcomes", ["YES", "NO"])
                
                market_price = {}
                for outcome in outcomes:
                    market_price[outcome] = self.polymarket.get_market_price(market_id, outcome)
                
                candidate = MarketCandidate(
                    market_id=market_id,
                    title=market_data.get("question", market_data.get("title", "")),
                    category=market_data.get("category", ""),
                    volume_24h=float(volume_24h),
                    liquidity=float(liquidity),
                    time_to_resolve=market_data.get("endDate", "Unknown"),
                    potential_edge="TBD",
                    priority_score=0.0,
                    outcomes=[{"name": o} for o in outcomes],
                    market_price=market_price
                )
                
                self.repo.save_market(self._market_to_db(market_data, liquidity))
                candidates.append(candidate)
                
            except Exception as e:
                logger.warning(f"ScannerAgent: Error processing market {market_id}: {e}")
                continue
        
        candidates = self._rank_candidates(candidates)
        
        logger.info(f"ScannerAgent: Found {len(candidates)} candidates after filtering")
        return candidates[:self.max_markets]
    
    def _rank_candidates(self, candidates: List[MarketCandidate]) -> List[MarketCandidate]:
        for candidate in candidates:
            score = 0.0
            
            score += min(candidate.liquidity / 10000, 3.0)
            
            score += min(candidate.volume_24h / 5000, 2.0)
            
            if candidate.time_to_resolve:
                try:
                    end_date = datetime.fromisoformat(candidate.time_to_resolve.replace("Z", "+00:00"))
                    days_to_resolve = (end_date - datetime.now()).days
                    if 1 <= days_to_resolve <= 30:
                        score += 2.0
                    elif 30 < days_to_resolve <= 90:
                        score += 1.0
                except:
                    pass
            
            candidate.priority_score = score
        
        return sorted(candidates, key=lambda x: x.priority_score, reverse=True)
    
    def _market_to_db(self, market_data: Dict, liquidity: float):
        from ..data_store.models import Market
        return Market(
            id=market_data.get("id", ""),
            title=market_data.get("question", market_data.get("title", "")),
            question=market_data.get("question", ""),
            description=market_data.get("description", ""),
            category=market_data.get("category", ""),
            outcomes=json.dumps(market_data.get("outcomes", [])),
            volume_24h=float(market_data.get("volume24hr", 0) or 0),
            liquidity=float(liquidity),
            end_date=market_data.get("endDate", ""),
            resolved=market_data.get("closed", False),
            winner=market_data.get("outcome", "")
        )
    
    def analyze_with_llm(self, candidates: List[MarketCandidate]) -> List[str]:
        if not candidates:
            return []
        
        candidates_data = [
            {
                "market_id": c.market_id,
                "title": c.title,
                "category": c.category,
                "volume_24h": c.volume_24h,
                "liquidity": c.liquidity,
                "time_to_resolve": c.time_to_resolve,
                "outcomes": c.outcomes
            }
            for c in candidates[:10]
        ]
        
        user_message = f"""Analyze these Polymarket market candidates and identify which ones have the highest potential for profitable trading based on mispricing opportunities:

{json.dumps(candidates_data, indent=2)}

Consider:
- Market liquidity and trading volume
- Time to resolution
- Category and current events relevance
- Potential for information asymmetry

Return JSON with market_ids ranked by priority for research."""

        response = self.llm.complete(
            system_prompt=SYSTEM_PROMPT_SCANNER,
            user_message=user_message,
            json_output=True
        )
        
        parsed = self.llm.parse_json_response(response)
        if parsed and "markets_to_research" in parsed:
            return parsed["markets_to_research"]
        
        return [c.market_id for c in candidates[:5]]
