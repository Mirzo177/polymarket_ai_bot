from typing import Dict, List, Optional, Tuple
from loguru import logger

from ..clients.price_client import PriceClient


class TrendFollowStrategy:
    def __init__(
        self,
        ma_short: int = 20,
        ma_long: int = 50,
        rsi_oversold: int = 30,
        rsi_overbought: int = 70
    ):
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.price_client = None
    
    def initialize(self):
        if self.price_client is None:
            self.price_client = PriceClient()
    
    def analyze(self, coin_id: str = "bitcoin") -> Dict:
        self.initialize()
        
        metrics = self.price_client.get_btc_metrics()
        
        if not metrics or not metrics.get("current_price"):
            return {"signal": "NO_SIGNAL", "reason": "Could not fetch price data"}
        
        signal = self._generate_signal(metrics)
        
        return {
            "signal": signal,
            "current_price": metrics.get("current_price"),
            "ma_20": metrics.get("ma_20"),
            "ma_50": metrics.get("ma_50"),
            "rsi_14": metrics.get("rsi_14"),
            "trend": metrics.get("trend"),
            "volatility": metrics.get("volatility_7d"),
            "price_change_24h": metrics.get("price_change_24h"),
            "recommendation": self._get_recommendation(signal, metrics)
        }
    
    def _generate_signal(self, metrics: Dict) -> str:
        ma_20 = metrics.get("ma_20")
        ma_50 = metrics.get("ma_50")
        rsi = metrics.get("rsi_14")
        current_price = metrics.get("current_price")
        
        if not all([ma_20, ma_50, rsi, current_price]):
            return "NO_SIGNAL"
        
        if rsi >= self.rsi_overbought:
            return "OVERBOUGHT"
        
        if rsi <= self.rsi_oversold:
            return "OVERSOLD"
        
        if current_price > ma_20 > ma_50:
            return "STRONG_BULLISH"
        
        if current_price > ma_20:
            return "BULLISH"
        
        if current_price < ma_20 < ma_50:
            return "STRONG_BEARISH"
        
        if current_price < ma_20:
            return "BEARISH"
        
        return "NEUTRAL"
    
    def _get_recommendation(self, signal: str, metrics: Dict) -> str:
        recommendations = {
            "STRONG_BULLISH": "Strong uptrend - suitable for YES bets on price UP markets",
            "BULLISH": "Moderate uptrend - consider small position YES bets",
            "NEUTRAL": "No clear trend - avoid directional bets",
            "BEARISH": "Moderate downtrend - consider small position NO bets",
            "STRONG_BEARISH": "Strong downtrend - suitable for YES bets on price DOWN markets",
            "OVERBOUGHT": "RSI extreme - reversal possible, reduce positions",
            "OVERSOLD": "RSI extreme - reversal possible, may add positions",
            "NO_SIGNAL": "Insufficient data - wait"
        }
        
        return recommendations.get(signal, "Unknown signal")
    
    def get_market_signal(self, signal: str, is_up_market: bool = True) -> Tuple[bool, float]:
        if signal == "NO_SIGNAL":
            return False, 0.0
        
        confidence_multiplier = {
            "STRONG_BULLISH": 1.0 if is_up_market else 0.5,
            "BULLISH": 0.7 if is_up_market else 0.4,
            "NEUTRAL": 0.5,
            "BEARISH": 0.4 if is_up_market else 0.7,
            "STRONG_BEARISH": 0.5 if is_up_market else 1.0,
            "OVERBOUGHT": 0.3,
            "OVERSOLD": 0.3
        }
        
        mult = confidence_multiplier.get(signal, 0.0)
        
        if signal in ["STRONG_BULLISH", "STRONG_BEARISH"]:
            return True, mult
        elif signal in ["BULLISH", "BEARISH"]:
            return True, mult
        elif signal == "NEUTRAL":
            return True, mult
        
        return False, mult
    
    def should_follow_trend(self, metrics: Dict) -> bool:
        rsi = metrics.get("rsi_14", 50)
        volatility = metrics.get("volatility_7d", 0)
        
        if rsi >= 70 or rsi <= 30:
            return False
        
        if volatility > 10:
            return False
        
        return True
