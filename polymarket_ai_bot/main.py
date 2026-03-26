import asyncio
import time
import signal
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger

from polymarket_ai_bot.config import get_config
from polymarket_ai_bot.logging_utils import setup_logging
from polymarket_ai_bot.llm.claude_client import ClaudeClient
from polymarket_ai_bot.clients.polymarket_client import PolymarketClient
from polymarket_ai_bot.clients.web_search_client import WebSearchClient
from polymarket_ai_bot.clients.price_client import PriceClient
from polymarket_ai_bot.data_store.repository import DatabaseRepository
from polymarket_ai_bot.agents.scanner_agent import ScannerAgent
from polymarket_ai_bot.agents.research_agent import ResearchAgent
from polymarket_ai_bot.agents.forecaster_agent import ForecasterAgent
from polymarket_ai_bot.agents.trader_agent import TraderAgent
from polymarket_ai_bot.agents.risk_manager_agent import RiskManagerAgent
from polymarket_ai_bot.agents.reviewer_agent import ReviewerAgent
from polymarket_ai_bot.tools.portfolio_utils import PortfolioUtils
from polymarket_ai_bot.strategies.value_bet import ValueBetStrategy
from polymarket_ai_bot.strategies.trend_follow import TrendFollowStrategy
from polymarket_ai_bot.strategies.simple_arb import SimpleArbitrageStrategy
from polymarket_ai_bot.data_store.models import Trade


class PolymarketTradingBot:
    def __init__(self):
        self.config = get_config()
        self.logger = setup_logging(self.config.LOG_LEVEL)
        
        self.logger.info("Initializing Polymarket Trading Bot...")
        
        self.llm_client = ClaudeClient()
        self.polymarket = PolymarketClient()
        self.web_search = WebSearchClient()
        self.price_client = PriceClient()
        self.repository = DatabaseRepository()
        
        self.scanner = ScannerAgent(
            self.llm_client,
            self.polymarket,
            self.repository
        )
        
        self.researcher = ResearchAgent(
            self.llm_client,
            self.web_search,
            self.polymarket,
            self.repository
        )
        
        self.forecaster = ForecasterAgent(
            self.llm_client,
            self.repository
        )
        
        self.trader = TraderAgent(
            self.llm_client,
            self.repository
        )
        
        self.risk_manager = RiskManagerAgent(
            self.llm_client,
            self.repository
        )
        
        self.reviewer = ReviewerAgent(
            self.llm_client,
            self.repository
        )
        
        self.portfolio_utils = PortfolioUtils(self.repository)
        
        self.value_strategy = ValueBetStrategy(
            min_edge=self.config.settings.strategies.value_bet.min_edge,
            kelly_fraction=self.config.settings.strategies.value_bet.kelly_fraction,
            max_bet_pct=self.config.settings.strategies.value_bet.max_bet_pct_portfolio
        )
        
        self.trend_strategy = TrendFollowStrategy(
            ma_short=self.config.settings.strategies.trend_follow.ma_short,
            ma_long=self.config.settings.strategies.trend_follow.ma_long,
            rsi_oversold=self.config.settings.strategies.trend_follow.rsi_oversold,
            rsi_overbought=self.config.settings.strategies.trend_follow.rsi_overbought
        )
        
        self.arb_strategy = SimpleArbitrageStrategy(
            min_price_deviation=self.config.settings.strategies.simple_arb.min_price_deviation,
            max_position_size=self.config.settings.strategies.simple_arb.max_position_size
        )
        
        self.running = False
        self.shutdown_requested = False
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.logger.info("Shutdown signal received...")
        self.shutdown_requested = True
    
    async def run_cycle(self):
        if self.shutdown_requested:
            return False
        
        cycle_start = time.time()
        self.logger.info("=== Starting Trading Cycle ===")
        
        try:
            if not self.risk_manager.check_daily_loss_limit():
                self.logger.warning("Daily loss limit exceeded, pausing trading")
                await asyncio.sleep(self.config.settings.global_settings.polling_interval_sec)
                return True
            
            self.logger.info("Step 1: Scanning for market opportunities...")
            candidates = self.scanner.run_step()
            
            if not candidates:
                self.logger.info("No market candidates found this cycle")
                await asyncio.sleep(self.config.settings.global_settings.polling_interval_sec)
                return True
            
            market_ids = self.scanner.analyze_with_llm(candidates)
            self.logger.info(f"Selected {len(market_ids)} markets for research: {market_ids}")
            
            proposals = []
            
            for market_id in market_ids[:self.config.settings.global_settings.max_markets_per_cycle]:
                if self.shutdown_requested:
                    break
                
                try:
                    self.logger.info(f"Processing market {market_id}")
                    
                    candidate = next((c for c in candidates if c.market_id == market_id), None)
                    if not candidate:
                        continue
                    
                    market_info = self.polymarket.get_market_info(market_id)
                    if not market_info:
                        continue
                    
                    research_data = self.researcher.run_step(market_id, candidate.title)
                    
                    forecast = self.forecaster.run_step(candidate, market_info, research_data)
                    
                    raw_proposals = self.trader.run_step(candidate, forecast, market_info)
                    
                    portfolio_exposure = self.portfolio_utils.calculate_exposure()
                    
                    risk_assessments = self.risk_manager.run_step(raw_proposals, portfolio_exposure)
                    
                    for proposal, assessment in zip(raw_proposals, risk_assessments):
                        if assessment.approved:
                            final_size = proposal.size if proposal.size is not None else 0.0
                            size_reduction = assessment.size_reduction_pct or 0.0
                            if size_reduction > 0:
                                final_size = final_size * (1 - size_reduction)
                            
                            final_proposal = proposal.copy()
                            final_proposal.size = final_size
                            final_proposal.expected_value = final_proposal.expected_value * (final_size / proposal.size) if proposal.size and proposal.size > 0 else 0
                            
                            proposals.append(final_proposal)
                            
                            self.logger.info(
                                f"APPROVED: {final_proposal.action} {final_proposal.size:.2f} "
                                f"{final_proposal.outcome} on {final_proposal.market_id} "
                                f"(edge: {final_proposal.edge:.2%})"
                            )
                        else:
                            self.logger.debug(
                                f"REJECTED: {proposal.market_id} - {', '.join(assessment.reasons[:2])}"
                            )
                
                except Exception as e:
                    self.logger.error(f"Error processing market {market_id}: {e}")
                    continue
            
            if proposals:
                self.logger.info(f"Executing {len(proposals)} approved trades...")
                await self._execute_proposals(proposals)
            else:
                self.logger.info("No approved trades this cycle")
            
            cycle_time = time.time() - cycle_start
            self.logger.info(f"Cycle completed in {cycle_time:.2f} seconds")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}")
            return True
    
    async def _execute_proposals(self, proposals: List[Dict]):
        for proposal in proposals:
            if self.shutdown_requested:
                break
            
            try:
                self.logger.info(
                    f"Executing: {proposal['action']} {proposal['size']:.2f} "
                    f"{proposal['outcome']} on {proposal['market_id']} @ ${proposal['price']:.4f}"
                )
                
                if self.config.IS_LIVE_MODE:
                    result = self.polymarket.place_order(
                        market_id=proposal['market_id'],
                        outcome=proposal['outcome'],
                        size=proposal['size'],
                        side=proposal['action'],
                        dry_run=False
                    )
                else:
                    result = self.polymarket.place_order(
                        market_id=proposal['market_id'],
                        outcome=proposal['outcome'],
                        size=proposal['size'],
                        side=proposal['action'],
                        dry_run=True
                    )
                
                trade = Trade(
                    id=result.get('order_id', f"trade_{int(time.time())}"),
                    market_id=proposal['market_id'],
                    market_title=proposal['market_title'],
                    order_id=result.get('order_id', ''),
                    strategy=proposal.get('strategy', 'unknown'),
                    side=proposal['action'],
                    outcome=proposal['outcome'],
                    size=proposal['size'],
                    price=proposal['price'],
                    cost=proposal['size'] * proposal['price'],
                    pnl=0,
                    reasoning=proposal.get('reasoning', ''),
                    status='FILLED' if result.get('status') in ['FILLED', 'SUBMITTED'] else 'PENDING',
                    simulated=self.config.IS_LIVE_MODE == False,
                    created_at=datetime.now().isoformat()
                )
                
                self.repository.save_trade(trade)
                
                self.logger.info(f"Trade executed and recorded: {trade.id}")
                
            except Exception as e:
                self.logger.error(f"Failed to execute proposal {proposal.get('market_id')}: {e}")
    
    async def run(self):
        self.logger.info("Starting Polymarket Trading Bot...")
        self.logger.info(f"Mode: {'LIVE' if self.config.IS_LIVE_MODE else 'PAPER'}")
        self.logger.info(f"Polling interval: {self.config.settings.global_settings.polling_interval_sec} seconds")
        
        self.running = True
        
        while self.running and not self.shutdown_requested:
            try:
                await self.run_cycle()
                
                if not self.shutdown_requested:
                    delay = self.config.settings.global_settings.polling_interval_sec
                    self.logger.info(f"Waiting {delay} seconds until next cycle...")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                self.logger.error(f"Unexpected error in main loop: {e}")
                await asyncio.sleep(5)
        
        self.logger.info("Trading bot stopped")
        self.running = False


async def main():
    bot = PolymarketTradingBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)