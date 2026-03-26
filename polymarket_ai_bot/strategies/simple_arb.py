from typing import List, Dict, Optional, Tuple
from loguru import logger


class SimpleArbitrageStrategy:
    def __init__(
        self,
        min_price_deviation: float = 0.02,
        max_position_size: float = 25.0
    ):
        self.min_price_deviation = min_price_deviation
        self.max_position_size = max_position_size
    
    def find_opportunities(
        self,
        markets: List[Dict]
    ) -> List[Dict]:
        opportunities = []
        
        for i, market in enumerate(markets):
            for j, other_market in enumerate(markets):
                if i >= j:
                    continue
                
                opp = self._check_arbitrage(market, other_market)
                if opp:
                    opportunities.append(opp)
        
        opportunities.sort(key=lambda x: x.get("edge", 0), reverse=True)
        
        return opportunities
    
    def _check_arbitrage(
        self,
        market1: Dict,
        market2: Dict
    ) -> Optional[Dict]:
        question1 = market1.get("question", "").lower()
        question2 = market2.get("question", "").lower()
        
        complementary = self._are_complementary(question1, question2)
        
        if not complementary:
            return None
        
        prices1 = market1.get("prices", {})
        prices2 = market2.get("prices", {})
        
        if not prices1 or not prices2:
            return None
        
        total_yes = sum(prices1.values()) + sum(prices2.values())
        
        edge = 1 - total_yes
        
        if edge < self.min_price_deviation:
            return None
        
        return {
            "market1_id": market1.get("id"),
            "market1_question": market1.get("question"),
            "market2_id": market2.get("id"),
            "market2_question": market2.get("question"),
            "market1_prices": prices1,
            "market2_prices": prices2,
            "combined_yes": total_yes,
            "edge": edge,
            "action": "SELL_BOTH" if total_yes > 1 else "BUY_BOTH",
            "position_size": self._calculate_size(edge)
        }
    
    def _are_complementary(self, q1: str, q2: str) -> bool:
        keywords = {
            ("yes", "no"),
            ("will", "won't"),
            ("happens", "doesn't happen"),
            ("higher", "lower"),
            ("above", "below")
        }
        
        q1_lower = q1.lower()
        q2_lower = q2.lower()
        
        for kw1, kw2 in keywords:
            if kw1 in q1_lower and kw2 in q2_lower:
                return True
            if kw2 in q1_lower and kw1 in q2_lower:
                return True
        
        return False
    
    def _calculate_size(self, edge: float) -> float:
        base_size = self.max_position_size
        
        if edge > 0.1:
            return base_size
        elif edge > 0.05:
            return base_size * 0.7
        elif edge > 0.02:
            return base_size * 0.4
        
        return base_size * 0.2
    
    def execute_arbitrage(
        self,
        opportunity: Dict
    ) -> List[Dict]:
        action = opportunity.get("action", "")
        
        if action == "SELL_BOTH":
            return [
                {
                    "market_id": opportunity["market1_id"],
                    "action": "SELL",
                    "outcome": "YES",
                    "size": opportunity["position_size"],
                    "reasoning": f"Arbitrage - combined edge {opportunity['edge']:.2%}"
                },
                {
                    "market_id": opportunity["market2_id"],
                    "action": "SELL",
                    "outcome": "YES",
                    "size": opportunity["position_size"],
                    "reasoning": f"Arbitrage - combined edge {opportunity['edge']:.2%}"
                }
            ]
        
        elif action == "BUY_BOTH":
            return [
                {
                    "market_id": opportunity["market1_id"],
                    "action": "BUY",
                    "outcome": "YES",
                    "size": opportunity["position_size"],
                    "reasoning": f"Arbitrage - combined discount {opportunity['edge']:.2%}"
                },
                {
                    "market_id": opportunity["market2_id"],
                    "action": "BUY",
                    "outcome": "YES",
                    "size": opportunity["position_size"],
                    "reasoning": f"Arbitrage - combined discount {opportunity['edge']:.2%}"
                }
            ]
        
        return []
    
    def check_market_inefficiency(
        self,
        outcomes: List[str],
        prices: Dict[str, float]
    ) -> Optional[Dict]:
        total = sum(prices.values())
        
        expected_sum = len(outcomes)
        
        deviation = abs(total - expected_sum)
        
        if deviation > self.min_price_deviation:
            return {
                "total": total,
                "expected": expected_sum,
                "deviation": deviation,
                "opportunity": "OVERPRICED" if total > expected_sum else "UNDERPRICED",
                "hedge_action": "SELL" if total > expected_sum else "BUY"
            }
        
        return None
