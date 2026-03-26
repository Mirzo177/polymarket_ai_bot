import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from ..llm.claude_client import ClaudeClient
from ..llm.prompts import SYSTEM_PROMPT_REVIEWER, REVIEW_SCHEMA
from ..data_store.repository import DatabaseRepository
from ..config import get_config


class ReviewerAgent:
    def __init__(
        self,
        llm_client: ClaudeClient,
        repository: DatabaseRepository
    ):
        self.llm = llm_client
        self.repo = repository
        self.config = get_config()
    
    def run_step(self, days: int = 7) -> Dict[str, Any]:
        logger.info(f"ReviewerAgent: Running performance review for last {days} days")
        
        trades = self.repo.get_trades(days=days)
        stats = self.repo.get_stats()
        
        if not trades:
            logger.info("ReviewerAgent: No trades to review")
            return {"status": "no_trades", "message": "No trades found for review period"}
        
        settled_trades = [t for t in trades if t.get("status") == "SETTLED"]
        all_trades = trades
        
        period_summary = self._generate_period_summary(all_trades, settled_trades)
        
        llm_review = self._generate_llm_review(all_trades, settled_trades, stats)
        
        review_data = {
            "period_start": (datetime.now() - timedelta(days=days)).isoformat(),
            "period_end": datetime.now().isoformat(),
            "total_trades": len(all_trades),
            "settled_trades": len(settled_trades),
            "stats": stats,
            "period_summary": period_summary,
            "llm_review": llm_review
        }
        
        self._save_review(review_data)
        
        logger.info(f"ReviewerAgent: Review complete")
        return review_data
    
    def _generate_period_summary(
        self,
        all_trades: List[Dict],
        settled_trades: List[Dict]
    ) -> str:
        if not all_trades:
            return "No trading activity in this period."
        
        total_pnl = sum(t.get("pnl", 0) for t in settled_trades)
        win_count = len([t for t in settled_trades if t.get("pnl", 0) > 0])
        loss_count = len([t for t in settled_trades if t.get("pnl", 0) < 0])
        win_rate = win_count / len(settled_trades) if settled_trades else 0
        
        strategies = {}
        for t in all_trades:
            strat = t.get("strategy", "unknown")
            strategies[strat] = strategies.get(strat, 0) + 1
        
        summary = f"""
Period Trading Summary:
- Total Trades: {len(all_trades)}
- Settled Trades: {len(settled_trades)}
- Win Rate: {win_rate:.1%}
- Total P&L: ${total_pnl:.2f}
- Wins: {win_count}, Losses: {loss_count}
- Strategies Used: {', '.join([f'{k}({v})' for k, v in strategies.items()])}
"""
        return summary.strip()
    
    def _generate_llm_review(
        self,
        all_trades: List[Dict],
        settled_trades: List[Dict],
        stats: Dict
    ) -> Dict[str, Any]:
        trades_json = json.dumps(all_trades[:50], indent=2)
        
        context = f"""
TRADING HISTORY (last 50 trades):
{trades_json}

PORTFOLIO STATS:
{json.dumps(stats, indent=2)}

RISK CONFIG:
{json.dumps(self.config.settings.risk.model_dump(), indent=2)}

STRATEGY CONFIG:
{json.dumps(self.config.settings.strategies.model_dump(), indent=2)}
"""

        user_message = f"""Review this trading history and provide a detailed performance analysis.

{context}

Identify:
1. Systematic mistakes in probability estimation
2. Patterns in winning vs losing trades
3. Parameter adjustments that could improve performance
4. Any code-level improvements needed

Be specific and actionable. Return JSON with:
- period_summary: brief overview
- win_rate: calculated win rate
- total_pnl: total profit/loss
- largest_win, largest_loss
- mistake_patterns: array of {{pattern, frequency, impact, recommendation}}
- parameter_suggestions: array of {{parameter, current_value, suggested_value, reasoning}}
- code_suggestions: array of {{file, change, reasoning}}
"""

        response = self.llm.complete(
            system_prompt=SYSTEM_PROMPT_REVIEWER,
            user_message=user_message,
            json_output=True
        )
        
        parsed = self.llm.parse_json_response(response)
        if parsed:
            return parsed
        
        return {
            "period_summary": "Review unavailable due to LLM error",
            "mistake_patterns": [],
            "parameter_suggestions": [],
            "code_suggestions": []
        }
    
    def _save_review(self, review_data: Dict):
        from ..data_store.models import Review
        
        review = Review(
            period_start=review_data.get("period_start", ""),
            period_end=review_data.get("period_end", ""),
            total_trades=review_data.get("total_trades", 0),
            win_rate=review_data.get("llm_review", {}).get("win_rate", 0),
            total_pnl=review_data.get("llm_review", {}).get("total_pnl", 0),
            report_json=json.dumps(review_data),
            parameter_changes="",
            status="COMPLETED"
        )
        
        self.repo.save_review(review)
    
    def get_recent_improvements(self) -> List[Dict]:
        reviews = self.repo.get_reviews(limit=5)
        
        suggestions = []
        for review in reviews:
            report = json.loads(review.get("report_json", "{}"))
            llm_review = report.get("llm_review", {})
            
            suggestions.extend(llm_review.get("parameter_suggestions", []))
            suggestions.extend(llm_review.get("code_suggestions", []))
        
        return suggestions
    
    def apply_suggestions(self, suggestions: List[Dict]) -> List[str]:
        applied = []
        
        for suggestion in suggestions:
            if "parameter" in suggestion:
                param = suggestion.get("parameter", "")
                value = suggestion.get("suggested_value", "")
                
                applied.append(f"Would apply: {param} = {value}")
        
        return applied
