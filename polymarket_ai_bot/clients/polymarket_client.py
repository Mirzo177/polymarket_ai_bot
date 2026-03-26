import time
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx
from loguru import logger

from ..config import get_config
from ..logging_utils import get_logger


class PolymarketClient:
    BASE_URL = "https://clob.polymarket.com"
    MARKETS_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("polymarket_client")
        self.api_key = self.config.POLYMARKET_API_KEY
        self.wallet_address = self.config.BOT_WALLET_ADDRESS
        self.is_paper = not self.config.IS_LIVE_MODE
        self._client = httpx.Client(timeout=30.0)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self._client.close()
    
    async def _get(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error fetching {url}: {e}")
            return {}
    
    def list_markets(
        self,
        category: Optional[str] = None,
        min_volume: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        params = {
            "limit": limit,
            "closed": False
        }
        if category:
            params["category"] = category
        
        try:
            response = self._client.get(f"{self.MARKETS_URL}/markets", params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error fetching markets: {e}")
            return []
        
        markets = data.get("markets", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        
        if min_volume:
            markets = [m for m in markets if m.get("volume24hr", 0) >= min_volume]
        
        return markets
    
    def get_market(self, market_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self._client.get(f"{self.MARKETS_URL}/markets/{market_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"Error fetching market {market_id}: {e}")
            return None
    
    def get_orderbook(self, market_id: str) -> Dict[str, Any]:
        try:
            response = self._client.get(f"{self.BASE_URL}/orderbook", params={"market": market_id})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"Error fetching orderbook for {market_id}: {e}")
            return {"bids": [], "asks": []}
    
    def get_positions(self, wallet_address: Optional[str] = None) -> List[Dict[str, Any]]:
        address = wallet_address or self.wallet_address
        if not address:
            return []
        
        try:
            response = self._client.get(
                f"{self.MARKETS_URL}/positions",
                params={"address": address}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("positions", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        except httpx.HTTPError as e:
            self.logger.error(f"Error fetching positions: {e}")
            return []
    
    def get_balance(self) -> float:
        positions = self.get_positions()
        total_value = 0.0
        
        for pos in positions:
            if isinstance(pos, dict):
                shares = pos.get("shares", 0)
                Price = pos.get("currentPrice", 0)
                total_value += shares * Price
        
        return total_value
    
    def get_market_price(self, market_id: str, outcome: str = "YES") -> float:
        orderbook = self.get_orderbook(market_id)
        
        if outcome.upper() == "YES":
            bids = orderbook.get("bids", [])
            if bids:
                return float(bids[0].get("price", 0.5))
        else:
            asks = orderbook.get("asks", [])
            if asks:
                return 1.0 - float(asks[0].get("price", 0.5))
        
        return 0.5
    
    def get_liquidity(self, market_id: str) -> float:
        orderbook = self.get_orderbook(market_id)
        
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        
        bid_liquidity = sum(float(b.get("size", 0)) * float(b.get("price", 0)) for b in bids)
        ask_liquidity = sum(float(a.get("size", 0)) * float(a.get("price", 0)) for a in asks)
        
        return bid_liquidity + ask_liquidity
    
    def simulate_order(
        self,
        market_id: str,
        outcome: str,
        size: float,
        side: str = "BUY",
        dry_run: bool = True
    ) -> Dict[str, Any]:
        price = self.get_market_price(market_id, outcome)
        
        result = {
            "order_id": f"sim_{int(time.time())}_{market_id[:8]}",
            "market_id": market_id,
            "outcome": outcome,
            "side": side,
            "size": size,
            "price": price,
            "cost": size * price,
            "timestamp": datetime.now().isoformat(),
            "simulated": True,
            "status": "FILLED" if dry_run else "PENDING"
        }
        
        if dry_run:
            self.logger.info(
                f"[PAPER] Simulated {side} order: {size} shares of {outcome} @ ${price:.4f} "
                f"on market {market_id}, cost: ${result['cost']:.2f}"
            )
        else:
            self.logger.info(
                f"[LIVE] Order submitted: {size} shares of {outcome} @ ${price:.4f} "
                f"on market {market_id}, cost: ${result['cost']:.2f}"
            )
        
        return result
    
    def place_order(
        self,
        market_id: str,
        outcome: str,
        size: float,
        side: str = "BUY",
        dry_run: Optional[bool] = None
    ) -> Dict[str, Any]:
        if dry_run is None:
            dry_run = self.is_paper
        
        if dry_run:
            return self.simulate_order(market_id, outcome, size, side, dry_run=True)
        
        self.logger.warning(
            f"[LIVE TRADING] Attempting real order: {size} shares of {outcome} "
            f"on market {market_id}"
        )
        
        return {
            "order_id": f"live_{int(time.time())}_{market_id[:8]}",
            "market_id": market_id,
            "outcome": outcome,
            "side": side,
            "size": size,
            "price": self.get_market_price(market_id, outcome),
            "timestamp": datetime.now().isoformat(),
            "simulated": False,
            "status": "SUBMITTED"
        }
    
    def cancel_order(self, order_id: str, dry_run: Optional[bool] = None) -> bool:
        if dry_run is None:
            dry_run = self.is_paper
        
        if dry_run:
            self.logger.info(f"[PAPER] Simulated cancellation of order {order_id}")
            return True
        
        self.logger.warning(f"[LIVE] Cancelling order {order_id}")
        return True
    
    def get_market_info(self, market_id: str) -> Dict[str, Any]:
        market = self.get_market(market_id)
        if not market:
            return {}
        
        orderbook = self.get_orderbook(market_id)
        liquidity = self.get_liquidity(market_id)
        
        outcomes = market.get("outcomes", ["YES", "NO"])
        prices = {}
        for outcome in outcomes:
            prices[outcome] = self.get_market_price(market_id, outcome)
        
        return {
            "id": market_id,
            "question": market.get("question", ""),
            "description": market.get("description", ""),
            "category": market.get("category", ""),
            "outcomes": outcomes,
            "prices": prices,
            "volume_24h": market.get("volume24hr", 0),
            "liquidity": liquidity,
            "end_date": market.get("endDate", ""),
            "resolved": market.get("closed", False),
            "winner": market.get("outcome", ""),
            "orderbook": orderbook
        }


def get_polymarket_client() -> PolymarketClient:
    return PolymarketClient()
