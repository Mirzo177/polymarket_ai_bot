from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger


class MetricsCalculator:
    @staticmethod
    def calculate_sharpe(returns: List[float], risk_free_rate: float = 0.0) -> float:
        if not returns or len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return 0.0
        
        return (mean_return - risk_free_rate) / std_dev
    
    @staticmethod
    def calculate_max_drawdown(pnl_history: List[float]) -> float:
        if not pnl_history:
            return 0.0
        
        peak = pnl_history[0]
        max_dd = 0.0
        
        for pnl in pnl_history:
            if pnl > peak:
                peak = pnl
            dd = (peak - pnl) / max(peak, 1)
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    @staticmethod
    def calculate_win_rate(trades: List[Dict]) -> float:
        if not trades:
            return 0.0
        
        wins = len([t for t in trades if t.get("pnl", 0) > 0])
        return wins / len(trades)
    
    @staticmethod
    def calculate_profit_factor(trades: List[Dict]) -> float:
        if not trades:
            return 0.0
        
        gross_wins = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
        gross_losses = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))
        
        if gross_losses == 0:
            return gross_wins if gross_wins > 0 else 0.0
        
        return gross_wins / gross_losses
    
    @staticmethod
    def calculate_average_win(trades: List[Dict]) -> float:
        wins = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0]
        return sum(wins) / len(wins) if wins else 0.0
    
    @staticmethod
    def calculate_average_loss(trades: List[Dict]) -> float:
        losses = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0]
        return sum(losses) / len(losses) if losses else 0.0
    
    @staticmethod
    def calculate_expectancy(trades: List[Dict]) -> float:
        if not trades:
            return 0.0
        
        win_rate = MetricsCalculator.calculate_win_rate(trades)
        avg_win = MetricsCalculator.calculate_average_win(trades)
        avg_loss = MetricsCalculator.calculate_average_loss(trades)
        
        return (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
    
    @staticmethod
    def get_portfolio_metrics(trades: List[Dict], days: int = 30) -> Dict:
        returns = []
        pnl_history = []
        running_pnl = 0
        
        for trade in trades:
            pnl = trade.get("pnl", 0)
            running_pnl += pnl
            pnl_history.append(running_pnl)
            
            if pnl != 0:
                returns.append(pnl)
        
        return {
            "total_trades": len(trades),
            "win_rate": MetricsCalculator.calculate_win_rate(trades),
            "profit_factor": MetricsCalculator.calculate_profit_factor(trades),
            "average_win": MetricsCalculator.calculate_average_win(trades),
            "average_loss": MetricsCalculator.calculate_average_loss(trades),
            "expectancy": MetricsCalculator.calculate_expectancy(trades),
            "sharpe_ratio": MetricsCalculator.calculate_sharpe(returns),
            "max_drawdown": MetricsCalculator.calculate_max_drawdown(pnl_history),
            "total_pnl": running_pnl
        }
