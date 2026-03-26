from typing import Tuple, Optional
from loguru import logger


class ValueBetStrategy:
    def __init__(
        self,
        min_edge: float = 0.05,
        kelly_fraction: float = 0.25,
        max_bet_pct: float = 0.05
    ):
        self.min_edge = min_edge
        self.kelly_fraction = kelly_fraction
        self.max_bet_pct = max_bet_pct
    
    def calculate_position_size(
        self,
        your_prob: float,
        market_price: float,
        portfolio_value: float,
        edge: float
    ) -> Tuple[float, float]:
        if abs(edge) < self.min_edge:
            return 0.0, 0.0
        
        if your_prob <= 0 or your_prob >= 1:
            return 0.0, 0.0
        
        if market_price <= 0 or market_price >= 1:
            return 0.0, 0.0
        
        b = (1 / market_price) - 1
        
        kelly = (b * your_prob - (1 - your_prob)) / b
        
        if kelly <= 0:
            return 0.0, 0.0
        
        kelly *= self.kelly_fraction
        
        max_bet = portfolio_value * self.max_bet_pct
        kelly = min(kelly, max_bet)
        
        expected_value = (your_prob * b * kelly) - ((1 - your_prob) * kelly)
        
        kelly = round(kelly, 2)
        expected_value = round(expected_value, 4)
        
        return kelly, expected_value
    
    def should_bet(
        self,
        your_prob: float,
        market_price: float,
        confidence: str = "MEDIUM"
    ) -> Tuple[bool, str]:
        edge = your_prob - market_price
        
        if abs(edge) < self.min_edge:
            return False, f"Edge {edge:.2%} below minimum {self.min_edge:.2%}"
        
        if confidence == "LOW":
            edge_threshold = self.min_edge * 2
            if abs(edge) < edge_threshold:
                return False, "Low confidence, requiring double edge"
        
        if market_price < 0.05:
            return False, "Market price too low, illiquid"
        
        if market_price > 0.95:
            return False, "Market price too high, limited upside"
        
        return True, f"Valid bet with edge {edge:.2%}"
    
    def get_optimal_outcome(
        self,
        outcomes: list,
        your_probs: list,
        market_prices: list
    ) -> Optional[int]:
        best_idx = None
        best_edge = 0
        
        for i in range(len(outcomes)):
            edge = your_probs[i] - market_prices[i]
            if edge > best_edge and edge > self.min_edge:
                best_edge = edge
                best_idx = i
        
        return best_idx
    
    def calculate_expected_value(
        self,
        your_prob: float,
        market_price: float,
        stake: float
    ) -> float:
        if market_price <= 0 or market_price >= 1:
            return 0.0
        
        b = (1 / market_price) - 1
        
        win_amount = stake * b
        lose_amount = stake
        
        ev = (your_prob * win_amount) - ((1 - your_prob) * lose_amount)
        
        return ev
    
    def calculate_kelly_fraction(
        self,
        win_prob: float,
        odds: float
    ) -> float:
        if odds <= 0 or win_prob <= 0:
            return 0.0
        
        p = win_prob
        q = 1 - p
        b = odds - 1
        
        if b <= 0:
            return 0.0
        
        f_star = (b * p - q) / b
        
        return max(0, min(f_star, 1))
