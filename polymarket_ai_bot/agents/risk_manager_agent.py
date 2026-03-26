import json
from typing import List, Dict, Any, Optional
from loguru import logger

from ..llm.claude_client import ClaudeClient
from ..llm.prompts import SYSTEM_PROMPT_RISK_MANAGER, RISK_ASSESSMENT_SCHEMA
from ..data_store.repository import DatabaseRepository
from ..data_store.models import TradeProposal, RiskAssessment
from ..config import get_config


class RiskManagerAgent:
    def __init__(
        self,
        llm_client: ClaudeClient,
        repository: DatabaseRepository
    ):
        self.llm = llm_client
        self.repo = repository
        self.config = get_config()
        self.risk_config = self.config.settings.risk
    
    def run_step(
        self,
        proposals: List[TradeProposal],
        portfolio_exposure: Dict
    ) -> List[RiskAssessment]:
        logger.info(f"RiskManagerAgent: Reviewing {len(proposals)} proposals")
        
        assessments = []
        
        for proposal in proposals:
            # Check for None values in critical fields
            if proposal.size is None or proposal.price is None or proposal.edge is None:
                reasons = ["Missing required data (size, price, or edge is None)"]
                assessment = RiskAssessment(
                    approved=False,
                    risk_score=1.0,
                    reasons=reasons,
                    size_reduction_pct=0.0,
                    conditional_notes="Invalid proposal data"
                )
                assessments.append(assessment)
                logger.warning(
                    f"RiskManagerAgent: REJECTED {proposal.market_id} - Missing required data"
                )
                continue
            
            assessment = self._assess_proposal(proposal, portfolio_exposure)
            assessments.append(assessment)
            
            if not assessment.approved:
                logger.warning(
                    f"RiskManagerAgent: REJECTED {proposal.market_id} - "
                    f"{', '.join(assessment.reasons[:2])}"
                )
        
        approved = [a for a in assessments if a.approved]
        logger.info(f"RiskManagerAgent: {len(approved)}/{len(proposals)} proposals approved")
        
        return assessments
    
    def _assess_proposal(
        self,
        proposal: TradeProposal,
        portfolio_exposure: Dict
    ) -> RiskAssessment:
        reasons = []
        risk_score = 0.0
        size_reduction = 0.0
        
        # Handle None values
        proposal_size = proposal.size if proposal.size is not None else 0.0
        proposal_price = proposal.price if proposal.price is not None else 0.0
        proposal_edge = proposal.edge if proposal.edge is not None else 0.0
        
        if proposal_size > self.risk_config.max_notional_per_market:
            reasons.append(f"Bet size ${proposal_size:.2f} exceeds max ${self.risk_config.max_notional_per_market:.2f}")
            risk_score += 0.3
            size_reduction = max(size_reduction, 0.5)
        
        total_exposure = (portfolio_exposure.get("total_exposure", 0) or 0) + proposal_size
        if total_exposure > self.risk_config.max_total_exposure:
            reasons.append(f"Total exposure would exceed max ${self.risk_config.max_total_exposure:.2f}")
            risk_score += 0.4
            size_reduction = max(size_reduction, 0.3)
        
        if abs(proposal_edge) < self.risk_config.min_edge_threshold:
            reasons.append(f"Edge {proposal_edge:.2%} below minimum {self.risk_config.min_edge_threshold:.2%}")
            risk_score += 0.2
        
        if proposal.confidence == "LOW":
            reasons.append("Low confidence forecast")
            risk_score += 0.15
        
        existing_positions = self.repo.get_positions(proposal.market_id)
        if existing_positions:
            reasons.append(f"Already have position in this market")
            risk_score += 0.1
            size_reduction = max(size_reduction, 0.2)
        
        if proposal_size * proposal_price > self.risk_config.max_position_per_outcome:
            reasons.append(f"Position size would exceed max per outcome")
            risk_score += 0.2
        
        if risk_score == 0 and reasons:
            risk_score = 0.1
        
        approved = risk_score < 0.3 and len(reasons) == 0
        
        if not approved and size_reduction > 0:
            adjusted_size = proposal.size * (1 - size_reduction)
            if adjusted_size < 1:
                approved = False
        
        return RiskAssessment(
            approved=approved,
            risk_score=risk_score,
            reasons=reasons,
            size_reduction_pct=size_reduction,
            conditional_notes=f"Reduce size by {size_reduction:.0%}" if size_reduction > 0 else ""
        )
    
    def check_daily_loss_limit(self) -> bool:
        daily_pnl = self.repo.get_daily_pnl()
        
        # Handle case where daily_pnl might be None
        if daily_pnl is None:
            # If we can't get PnL data, assume no loss and continue trading
            return True
        
        if daily_pnl < 0:
            loss_pct = abs(daily_pnl) / max(self.repo.get_portfolio_value(), 1) * 100
        else:
            loss_pct = 0
        
        if loss_pct >= self.risk_config.max_daily_loss_pct:
            logger.warning(
                f"RiskManagerAgent: Daily loss {loss_pct:.2f}% exceeds max "
                f"{self.risk_config.max_daily_loss_pct:.2f}%. Trading halted."
            )
            return False
        
        return True
    
    def assess_llm(
        self,
        proposal: TradeProposal,
        portfolio_exposure: Dict
    ) -> RiskAssessment:
        context = f"""
PROPOSAL:
Market: {proposal.market_title}
Market ID: {proposal.market_id}
Action: {proposal.action} {proposal.outcome}
Size: ${proposal.size:.2f}
Price: ${proposal.price:.4f}
Edge: {proposal.edge:.2%}
Expected Value: {proposal.expected_value:.4f}
Confidence: {proposal.confidence}
Strategy: {proposal.strategy}
Reasoning: {proposal.reasoning}

PORTFOLIO STATUS:
Total Exposure: ${portfolio_exposure.get('total_exposure', 0):.2f}
Position Count: {portfolio_exposure.get('position_count', 0)}
Available Capital: ${portfolio_exposure.get('available', 0):.2f}

RISK LIMITS:
Max Notional Per Market: ${self.risk_config.max_notional_per_market:.2f}
Max Total Exposure: ${self.risk_config.max_total_exposure:.2f}
Max Daily Loss %: {self.risk_config.max_daily_loss_pct:.2f}%
Min Edge Threshold: {self.risk_config.min_edge_threshold:.2%}
Max Position Per Outcome: ${self.risk_config.max_position_per_outcome:.2f}
"""

        user_message = f"""As an ultra-conservative Chief Risk Officer, evaluate this trade proposal against all risk limits.

{context}

Consider:
1. Does this breach any hard limits?
2. Is the risk/reward ratio acceptable?
3. Are there correlated positions creating hidden risk?
4. Should position size be reduced?

Return JSON with:
- approved: boolean (true only if no significant risks)
- risk_score: 0.0 to 1.0 (higher = more risky)
- reasons: array of specific risk concerns
- adjustments: {{size_reduction_pct, conditional_notes}} if needed

Be VERY conservative. Only approve if clearly safe."""

        response = self.llm.complete(
            system_prompt=SYSTEM_PROMPT_RISK_MANAGER,
            user_message=user_message,
            json_output=True
        )
        
        parsed = self.llm.parse_json_response(response)
        if parsed:
            return RiskAssessment(
                approved=parsed.get("approved", False),
                risk_score=parsed.get("risk_score", 0.5),
                reasons=parsed.get("reasons", []),
                size_reduction_pct=parsed.get("adjustments", {}).get("size_reduction_pct", 0),
                conditional_notes=parsed.get("adjustments", {}).get("conditional_notes", "")
            )
        
        return RiskAssessment(approved=False, risk_score=0.5, reasons=["LLM assessment unavailable"])
