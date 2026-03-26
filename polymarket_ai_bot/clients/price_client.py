import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
from loguru import logger

from ..config import get_config
from ..logging_utils import get_logger


class PriceClient:
    COINGECKO_BASE = "https://api.coingecko.com/api/v3"
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("price_client")
        self._client = httpx.Client(timeout=30.0)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self._client.close()
    
    def get_price(self, coin_id: str = "bitcoin", currency: str = "usd") -> Optional[float]:
        try:
            url = f"{self.COINGECKO_BASE}/simple/price"
            params = {
                "ids": coin_id,
                "vs_currencies": currency
            }
            response = self._client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get(coin_id, {}).get(currency)
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to get price for {coin_id}: {e}")
            return None
    
    def get_prices(self, coin_ids: List[str], currency: str = "usd") -> Dict[str, float]:
        try:
            url = f"{self.COINGECKO_BASE}/simple/price"
            params = {
                "ids": ",".join(coin_ids),
                "vs_currencies": currency
            }
            response = self._client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return {
                coin_id: data.get(coin_id, {}).get(currency, 0)
                for coin_id in coin_ids
            }
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to get prices: {e}")
            return {}
    
    def get_price_history(
        self,
        coin_id: str = "bitcoin",
        days: int = 30,
        currency: str = "usd"
    ) -> List[Dict[str, Any]]:
        try:
            url = f"{self.COINGECKO_BASE}/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": currency,
                "days": days,
                "interval": "daily" if days > 1 else "hourly"
            }
            response = self._client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            prices = data.get("prices", [])
            
            return [
                {
                    "timestamp": int(price[0] / 1000),
                    "datetime": datetime.fromtimestamp(price[0] / 1000).isoformat(),
                    "price": price[1]
                }
                for price in prices
            ]
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to get price history for {coin_id}: {e}")
            return []
    
    def calculate_ma(self, prices: List[float], period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def get_btc_metrics(self) -> Dict[str, Any]:
        price_history = self.get_price_history("bitcoin", days=60)
        
        if not price_history:
            return {}
        
        prices = [p["price"] for p in price_history]
        current_price = prices[-1] if prices else 0
        
        ma_20 = self.calculate_ma(prices, 20)
        ma_50 = self.calculate_ma(prices, 50)
        rsi_14 = self.calculate_rsi(prices, 14)
        
        price_change_24h = 0
        if len(prices) >= 2:
            price_change_24h = ((prices[-1] - prices[-2]) / prices[-2]) * 100
        
        volatility = 0
        if len(prices) >= 7:
            returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = (variance ** 0.5) * 100
        
        return {
            "current_price": current_price,
            "ma_20": ma_20,
            "ma_50": ma_50,
            "rsi_14": rsi_14,
            "price_change_24h": price_change_24h,
            "volatility_7d": volatility,
            "trend": "BULLISH" if ma_20 and ma_50 and ma_20 > ma_50 else "BEARISH",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_market_info(self, coin_ids: List[str] = None) -> List[Dict[str, Any]]:
        if coin_ids is None:
            coin_ids = ["bitcoin", "ethereum"]
        
        try:
            url = f"{self.COINGECKO_BASE}/coins/markets"
            params = {
                "vs_currency": "usd",
                "ids": ",".join(coin_ids),
                "order": "market_cap_desc",
                "per_page": 20
            }
            response = self._client.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to get market info: {e}")
            return []


def get_price_client() -> PriceClient:
    return PriceClient()
