import json
from typing import List, Dict, Any, Optional
from loguru import logger

from ..llm.claude_client import ClaudeClient
from ..llm.prompts import SYSTEM_PROMPT_TRADER, TRADE_PROPOSAL_SCHEMA
from ..data_store.repository import DatabaseRepository
from ..data_store.models import TradeProposal, MarketCandidate, Forecast
from ..strategies.value_bet import ValueBetStrategy
from ..config import get_config


class TraderAgent:
    def __init__(
        self,
        llm_client: ClaudeClient,
        repository: DatabaseRepository
    ):
        self.llm = llm_client
        self.repo = repository
        self.config = get_config()
        self.value_strategy = ValueBetStrategy(
            min_edge=self.config.settings.strategies.value_bet.min_edge,
            kelly_fraction=self.config.settings.strategies.value_bet.kelly_fraction,
            max_bet_pct=self.config.settings.strategies.value_bet.max_bet_pct_portfolio
        )
        self.portfolio_value = 1000.0
    
    def run_step(
        self,
        candidate: MarketCandidate,
        forecast: Forecast,
        market_info: Dict,
        research_data: Any = None
    ) -> List[TradeProposal]:
        logger.info(f"TraderAgent: Generating trade proposals for {candidate.market_id}")
        
        proposals = []
        
        proposals.extend(self._generate_value_bets(candidate, forecast))
        
        proposals = self._rank_proposals(proposals)
        
        logger.info(f"TraderAgent: Generated {len(proposals)} trade proposals")
        return proposals
    
    def _generate_value_bets(
        self,
        candidate: MarketCandidate,
        forecast: Forecast
    ) -> List[TradeProposal]:
        proposals = []
        
        for outcome in forecast.outcomes:
            name = outcome.get("name", "")
            your_prob = outcome.get("probability", 0.5)
            market_price = candidate.market_price.get(name, 0.5)
            
            edge = your_prob - market_price
            
            if abs(edge) < self.config.settings.risk.min_edge_threshold:
                continue
            
            size, ev = self.value_strategy.calculate_position_size(
                your_prob=your_prob,
                market_price=market_price,
                portfolio_value=self.portfolio_value,
                edge=edge
            )
            
            if size <= 0:
                continue
            
            action = "BUY" if edge > 0 else "SELL"
            
            proposal = TradeProposal(
                market_id=candidate.market_id,
                market_title=candidate.title,
                action=action,
                outcome=name,
                size=size,
                price=market_price,
                expected_value=ev,
                edge=edge,
                confidence=outcome.get("confidence", "MEDIUM"),
                reasoning=f"Value bet: Your prob {your_prob:.2%} vs market {market_price:.2%}, edge={edge:.2%}",
                strategy="value_bet"
            )
            proposals.append(proposal)
            
            logger.info(
                f"TraderAgent: {action} proposal - {name} @ ${market_price:.4f}, "
                f"size=${size:.2f}, edge={edge:.2%}, EV={ev:.4f}"
            )
        
        return proposals
    
    def _rank_proposals(self, proposals: List[TradeProposal]) -> List[TradeProposal]:
        scored_proposals = []
        for proposal in proposals:
            score = 0.0
            
            score += abs(proposal.edge) * 10
            
            if proposal.confidence == "HIGH":
                score *= 1.5
            elif proposal.confidence == "LOW":
                score *= 0.5
            
            if proposal.edge > 0.1:
                score *= 1.3
            
            score += proposal.expected_value * 5
            
            scored_proposals.append((proposal, score))
        
        scored_proposals.sort(key=lambda x: x[1], reverse=True)
        return [proposal for proposal, _ in scored_proposals]
    
    def calculate_kelly_size(
        self,
        win_prob: float,
        odds: float,
        kelly_fraction: float = 0.25,
        max_size: float = 100.0
    ) -> float:
        if odds <= 0 or win_prob <= 0:
            return 0.0
        
        b = odds - 1
        
        win = win_prob
        lose = 1 - win_prob
        
        q = lose
        p = win
        
        if b == 0:
            return 0.0
        
        f_star = (b * p - q) / b
        
        if f_star <= 0:
            return 0.0
        
        kelly_size = f_star * kelly_fraction
        
        max_bet = max_size
        kelly_size = min(kelly_size, max_bet)
        
        return round(kelly_size, 2)
    
    def get_portfolio_exposure(self) -> Dict[str, float]:
        positions = self.repo.get_positions()
        
        exposure = 0.0
        for pos in positions:
            exposure += pos.get("current_value", 0)
        
        return {
            "total_exposure": exposure,
            "position_count": len(positions),
            "available": self.portfolio_value - exposure
        }
