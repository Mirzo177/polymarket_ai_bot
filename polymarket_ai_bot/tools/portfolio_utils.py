from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from ..data_store.repository import DatabaseRepository


class PortfolioUtils:
    def __init__(self, repository: DatabaseRepository):
        self.repo = repository
    
    def calculate_exposure(self) -> Dict[str, Any]:
        positions = self.repo.get_positions()
        
        exposure_by_market: Dict[str, float] = {}
        total_exposure = 0.0
        
        for pos in positions:
            market_id = str(pos.get("market_id", ""))
            current_value = float(pos.get("current_value", 0))
            
            if market_id not in exposure_by_market:
                exposure_by_market[market_id] = 0.0
            exposure_by_market[market_id] += current_value
            
            total_exposure += current_value
        
        return {
            "total_exposure": total_exposure,
            "by_market": exposure_by_market,
            "position_count": len(positions)
        }
    
    def calculate_pnl(self) -> Dict[str, Any]:
        trades = self.repo.get_trades()
        
        total_pnl = 0.0
        realized_pnl = 0.0
        unrealized_pnl = 0.0
        win_count = 0
        loss_count = 0
        
        for trade in trades:
            pnl = float(trade.get("pnl", 0))
            status = str(trade.get("status", ""))
            
            if status in ["SETTLED", "FILLED"]:
                total_pnl += pnl
                if pnl > 0:
                    win_count += 1
                    realized_pnl += pnl
                elif pnl < 0:
                    loss_count += 1
                    realized_pnl += pnl
            elif status == "OPEN":
                unrealized_pnl += pnl
        
        total_trades = win_count + loss_count
        win_rate = win_count / total_trades if total_trades > 0 else 0.0
        
        return {
            "total_pnl": total_pnl,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "total_trades": total_trades
        }
    
    def get_drawdown(self, lookback_days: int = 30) -> Dict[str, Any]:
        daily_pnls = self._get_daily_pnl_series(lookback_days)
        
        if not daily_pnls:
            return {"max_drawdown": 0.0, "current_drawdown": 0.0, "drawdown_duration": 0}
        
        cumulative: List[float] = []
        running_total = 0.0
        for pnl in daily_pnls:
            running_total += pnl
            cumulative.append(running_total)
        
        peak = 0.0
        max_dd = 0.0
        current_dd = 0.0
        dd_duration = 0
        current_duration = 0
        
        for value in cumulative:
            if value > peak:
                peak = value
                current_dd = 0.0
                current_duration = 0
            else:
                dd = peak - value
                if dd > max_dd:
                    max_dd = dd
                current_dd = dd
                current_duration += 1
                if current_duration > dd_duration:
                    dd_duration = current_duration
        
        return {
            "max_drawdown": max_dd,
            "current_drawdown": current_dd,
            "drawdown_duration": dd_duration
        }
    
    def _get_daily_pnl_series(self, days: int) -> List[float]:
        daily_pnls: List[float] = [0.0] * days
        
        trades = self.repo.get_trades(days=days)
        
        for trade in trades:
            created_str = str(trade.get("created_at", ""))
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                days_ago = (datetime.now() - created).days
                if 0 <= days_ago < days:
                    daily_pnls[days_ago - 1] += float(trade.get("pnl", 0))
            except:
                pass
        
        return daily_pnls
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        daily_pnls = self._get_daily_pnl_series(30)
        
        if len(daily_pnls) < 2:
            return 0.0
        
        import statistics
        
        mean_return = statistics.mean(daily_pnls)
        if len(daily_pnls) > 1:
            std_return = statistics.stdev(daily_pnls)
        else:
            std_return = 0.0
        
        if std_return == 0:
            return 0.0
        
        excess_return = mean_return - (risk_free_rate / 252)
        
        return excess_return / std_return if std_return != 0 else 0.0
    
    def get_position_summary(self) -> List[Dict[str, Any]]:
        positions = self.repo.get_positions()
        
        summary: List[Dict[str, Any]] = []
        for pos in positions:
            cost = float(pos.get("cost", 0))
            unrealized_pnl = float(pos.get("unrealized_pnl", 0))
            roi_pct = (unrealized_pnl / cost * 100) if cost > 0 else 0.0
            
            summary.append({
                "market_id": str(pos.get("market_id", "")),
                "market_title": str(pos.get("market_title", "")),
                "outcome": str(pos.get("outcome", "")),
                "shares": float(pos.get("shares", 0)),
                "avg_price": float(pos.get("avg_price", 0)),
                "cost": cost,
                "current_value": float(pos.get("current_value", 0)),
                "unrealized_pnl": unrealized_pnl,
                "roi_pct": roi_pct
            })
        
        return summary
    
    def rebalance_suggestion(self, max_per_market: float = 100.0) -> List[Dict[str, Any]]:
        exposure_result = self.calculate_exposure()
        exposure_by_market = exposure_result["by_market"]
        suggestions: List[Dict[str, Any]] = []
        
        for market_id, amount in exposure_by_market.items():
            if float(amount) > max_per_market:
                suggestions.append({
                    "market_id": str(market_id),
                    "current_exposure": float(amount),
                    "suggested_exposure": max_per_market,
                    "action": "REDUCE",
                    "amount_to_reduce": float(amount) - max_per_market
                })
        
        return suggestions


def calculate_kelly_bet(win_prob: float, odds: float, fraction: float = 0.25) -> float:
    if odds <= 1 or win_prob <= 0 or win_prob >= 1:
        return 0.0
    
    b = odds - 1
    p = win_prob
    q = 1 - p
    
    kelly = (b * p - q) / b
    
    if kelly <= 0:
        return 0.0
    
    return kelly * fraction


def calculate_expected_value(prob_win: float, prob_loss: float, 
                           win_amount: float, loss_amount: float) -> float:
    return (prob_win * win_amount) + (prob_loss * loss_amount)
