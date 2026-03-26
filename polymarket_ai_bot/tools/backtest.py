import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger


class BacktestEngine:
    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = []
        self.trades = []
    
    def run(
        self,
        historical_data: List[Dict],
        strategy_func,
        parameters: Dict = None
    ) -> Dict:
        if parameters is None:
            parameters = {}
        
        logger.info(f"Starting backtest with {len(historical_data)} data points")
        
        # Reset state
        self.current_capital = self.initial_capital
        self.positions = []
        self.trades = []
        
        # Run backtest simulation
        for i, data_point in enumerate(historical_data):
            try:
                # Get strategy signal
                signal = strategy_func(data_point, parameters, self)
                
                # Execute trades based on signal
                if signal:
                    self._execute_signal(signal, data_point, i)
                    
            except Exception as e:
                logger.warning(f"Backtest error at index {i}: {e}")
                continue
        
        results = {
            "initial_capital": self.initial_capital,
            "final_capital": self.current_capital,
            "total_trades": len(self.trades),
            "winning_trades": len([t for t in self.trades if t.get("pnl", 0) > 0]),
            "losing_trades": len([t for t in self.trades if t.get("pnl", 0) < 0]),
            "total_pnl": self.current_capital - self.initial_capital,
            "win_rate": len([t for t in self.trades if t.get("pnl", 0) > 0]) / len(self.trades) if self.trades else 0,
            "max_drawdown": self._calculate_max_drawdown(),
            "trades": self.trades.copy()
        }
        
        return results
    
    def _execute_signal(self, signal: Dict, data_point: Dict, index: int):
        action = signal.get("action")
        market_id = signal.get("market_id")
        outcome = signal.get("outcome")
        size = signal.get("size", 0)
        price = signal.get("price", 0)
        
        if not all([action, market_id, outcome]) or size <= 0:
            return
        
        # Simulate trade execution
        trade = {
            "id": f"bt_{len(self.trades)}_{index}",
            "market_id": market_id,
            "market_title": data_point.get("title", ""),
            "order_id": f"bt_order_{len(self.trades)}",
            "strategy": signal.get("strategy", "backtest"),
            "side": action,
            "outcome": outcome,
            "size": size,
            "price": price,
            "cost": size * price,
            "pnl": 0,  # Will be calculated when resolved
            "reasoning": signal.get("reasoning", ""),
            "status": "OPEN",
            "simulated": True,
            "created_at": datetime.now().isoformat(),
            "resolved_at": None
        }
        
        self.trades.append(trade)
        self.current_capital -= size * price
        
        # Add position
        position = {
            "id": f"pos_{len(self.positions)}",
            "market_id": market_id,
            "market_title": data_point.get("title", ""),
            "outcome": outcome,
            "shares": size,
            "avg_price": price,
            "cost": size * price,
            "current_value": size * price,
            "unrealized_pnl": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.positions.append(position)
    
    def resolve_trade(self, trade_id: str, resolved_price: float):
        for trade in self.trades:
            if trade.get("id") == trade_id and trade.get("status") == "OPEN":
                # Calculate PnL
                size = trade.get("size", 0)
                entry_price = trade.get("price", 0)
                
                if trade.get("side") == "BUY":
                    pnl = size * (resolved_price - entry_price)
                else:  # SELL
                    pnl = size * (entry_price - resolved_price)
                
                trade["pnl"] = pnl
                trade["status"] = "SETTLED"
                trade["resolved_at"] = datetime.now().isoformat()
                
                # Update capital
                self.current_capital += size * entry_price + pnl
                
                # Update position
                for pos in self.positions:
                    if pos.get("market_id") == trade.get("market_id"):
                        pos["current_value"] = size * resolved_price
                        pos["unrealized_pnl"] = pos["current_value"] - pos["cost"]
                        break
                break
    
    def _calculate_max_drawdown(self) -> float:
        if not self.trades:
            return 0.0
        
        # Create equity curve
        equity = [self.initial_capital]
        running_capital = self.initial_capital
        
        for trade in sorted(self.trades, key=lambda x: x.get("created_at", "")):
            if trade.get("status") == "SETTLED":
                running_capital += trade.get("pnl", 0)
                equity.append(running_capital)
        
        if len(equity) < 2:
            return 0.0
        
        # Calculate drawdown
        peak = equity[0]
        max_drawdown = 0.0
        
        for value in equity:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def calculate_returns(self) -> List[float]:
        returns = []
        
        for trade in self.trades:
            if trade.get("status") == "SETTLED":
                pnl = trade.get("pnl", 0)
                if self.initial_capital > 0:
                    returns.append(pnl / self.initial_capital)
        
        return returns
    
    def get_summary(self) -> Dict:
        settled_trades = [t for t in self.trades if t.get("status") == "SETTLED"]
        
        if not settled_trades:
            return {
                "initial_capital": self.initial_capital,
                "final_capital": self.current_capital,
                "total_return": 0,
                "total_trades": 0,
                "open_positions": len([t for t in self.trades if t.get("status") == "OPEN"])
            }
        
        total_pnl = sum(t.get("pnl", 0) for t in settled_trades)
        wins = [t for t in settled_trades if t.get("pnl", 0) > 0]
        losses = [t for t in settled_trades if t.get("pnl", 0) < 0]
        
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.initial_capital + total_pnl,
            "total_return": (total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0,
            "total_trades": len(settled_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": len(wins) / len(settled_trades) if settled_trades else 0,
            "total_pnl": total_pnl,
            "avg_win": sum(t.get("pnl", 0) for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t.get("pnl", 0) for t in losses) / len(losses) if losses else 0,
            "max_drawdown": self._calculate_max_drawdown(),
            "open_positions": len([t for t in self.trades if t.get("status") == "OPEN"])
        }


def simple_value_bet_strategy(data_point: Dict, params: Dict, engine: BacktestEngine) -> Optional[Dict]:
    """Simple value bet strategy for backtesting"""
    # This is a placeholder - in reality would use your actual strategy logic
    if data_point.get("edge", 0) > params.get("min_edge", 0.05):
        return {
            "action": "BUY" if data_point.get("edge", 0) > 0 else "SELL",
            "market_id": data_point.get("market_id", ""),
            "outcome": data_point.get("outcome", "YES"),
            "size": min(params.get("base_size", 10), engine.current_capital * 0.05),
            "price": data_point.get("price", 0.5),
            "strategy": "value_bet",
            "reasoning": f"Edge: {data_point.get('edge', 0):.2%}"
        }
    return None
