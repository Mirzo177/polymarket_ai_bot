#!/usr/bin/env python3
"""
ADVANCED QUANT TRADING ENGINE
Mathematical models, multiple strategies, order flow analysis, Kelly criterion
Based on research from:
- $1,400 → $238,000 student story (scanning inefficiencies)
- Navnoor Bawa's quantitative prediction system
- Binary outcome trading strategies
"""
import os
import json
import time
import uuid
import math
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

# Builder credentials
os.environ['POLY_BUILDER_KEY'] = '019d2b2f-b867-7daf-ac0b-92da916743fd'
os.environ['POLY_BUILDER_SECRET'] = 'g8_tldos1eNeC1Ri6Itnaz49ibSBRCQKhYQCgK30qos='
os.environ['POLY_BUILDER_PASSPHRASE'] = 'bd017fc2ea140a60e42763d2383935fa6dd33b0d972ba08f7bf96d0c5cc41059'

from polymarket_apis import PolymarketGammaClient, PolymarketReadOnlyClobClient
import httpx


# ==================== MATHEMATICAL FOUNDATIONS ====================

class ProbabilityEstimator:
    """Bayesian model aggregation for probability estimation"""
    
    def __init__(self):
        self.weights = {
            'fundamental': 0.30,
            'market': 0.25,
            'sentiment': 0.20,
            'technical': 0.15,
            'momentum': 0.10
        }
    
    def estimate(self, market_data: Dict, news: List[Dict], price_history: List[float]) -> Dict:
        """Combine multiple probability estimates using Bayesian aggregation"""
        
        # 1. Market-based probability (current price)
        market_prob = market_data.get('price_yes', 0.5)
        
        # 2. Fundamental probability (from analysis)
        fundamental_prob = self._estimate_fundamental(market_data)
        
        # 3. Sentiment probability (from news)
        sentiment_prob = self._estimate_sentiment(news)
        
        # 4. Technical probability (from price history)
        technical_prob = self._estimate_technical(price_history)
        
        # 5. Momentum probability (from recent price changes)
        momentum_prob = self._estimate_momentum(price_history)
        
        # Bayesian aggregation
        posterior = (
            self.weights['fundamental'] * fundamental_prob +
            self.weights['market'] * market_prob +
            self.weights['sentiment'] * sentiment_prob +
            self.weights['technical'] * technical_prob +
            self.weights['momentum'] * momentum_prob
        )
        
        # Calculate confidence based on agreement between estimates
        estimates = [fundamental_prob, market_prob, sentiment_prob, technical_prob, momentum_prob]
        confidence = 1 - (np.std(estimates) / max(np.mean(estimates), 0.01))
        
        return {
            'probability': posterior,
            'confidence': max(0, min(1, confidence)),
            'components': {
                'fundamental': fundamental_prob,
                'market': market_prob,
                'sentiment': sentiment_prob,
                'technical': technical_prob,
                'momentum': momentum_prob
            }
        }
    
    def _estimate_fundamental(self, market_data: Dict) -> float:
        """Estimate based on market fundamentals - REALISTIC"""
        q = market_data.get('question', '').lower()
        vol = market_data.get('volume', 0)
        
        # Base probability from current market price (most efficient estimate)
        market_price = market_data.get('price_yes', 0.5)
        
        # Adjustments based on known biases
        base = market_price
        
        # Known inefficiencies:
        # - NHL teams at 0-1% are likely undervalued (they have SOME chance)
        # - "Jesus Christ return" at 48% is clearly overvalued (essentially impossible)
        # - GTA VI before June 2026 unlikely
        # - Sports underdogs often undervalued
        
        if 'jesus christ' in q:
            base = 0.02  # Essentially impossible
        elif 'nhl' in q or 'stanley cup' in q:
            # Teams priced at 0-1% probably have 5-15% chance
            if market_price < 0.05:
                base = min(0.15, market_price * 3)  # Up to 15%
            else:
                base = market_price
        elif 'gta' in q:
            if 'june 2026' in q:
                base = 0.05  # Very unlikely
            else:
                base = market_price
        elif 'world cup' in q or 'fifa' in q:
            # Teams priced very low have some chance
            if market_price < 0.10:
                base = min(0.20, market_price * 2)
            else:
                base = market_price
        
        return max(0.01, min(0.99, base))
    
    def _estimate_sentiment(self, news: List[Dict]) -> float:
        """Estimate based on news sentiment"""
        if not news:
            return 0.5
        
        sentiment_score = 0
        for article in news:
            title = article.get('title', '').lower()
            if any(w in title for w in ['bullish', 'up', 'positive', 'growth', 'win', 'success']):
                sentiment_score += 0.1
            elif any(w in title for w in ['bearish', 'down', 'negative', 'fail', 'lose', 'risk']):
                sentiment_score -= 0.1
        
        return 0.5 + (sentiment_score / len(news)) * 0.3
    
    def _estimate_technical(self, price_history: List[float]) -> float:
        """Technical analysis using Bollinger Bands and mean reversion"""
        if len(price_history) < 5:
            return 0.5
        
        prices = np.array(price_history[-20:])  # Last 20 data points
        mean = np.mean(prices)
        std = np.std(prices)
        current = prices[-1]
        
        # Bollinger Band position
        if std > 0:
            z_score = (current - mean) / std
            # Mean reversion: price below band = UP, above = DOWN
            # Convert to probability
            prob = 0.5 - (z_score * 0.1)
            return max(0.1, min(0.9, prob))
        
        return 0.5
    
    def _estimate_momentum(self, price_history: List[float]) -> float:
        """Momentum-based probability"""
        if len(price_history) < 3:
            return 0.5
        
        # Calculate momentum
        recent = price_history[-3:]
        changes = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
        avg_change = np.mean(changes)
        
        # Momentum probability
        return 0.5 + (avg_change * 2)


class KellyCriterion:
    """Fractional Kelly criterion with risk adjustments"""
    
    def __init__(self, fraction: float = 0.25):
        self.fraction = fraction  # Fractional Kelly (0.25 = quarter Kelly)
        self.max_kelly = 0.25  # Max position size as fraction of bankroll
    
    def calculate(self, probability: float, odds: float, confidence: float = 1.0) -> Dict:
        """
        Kelly formula: f* = (bp - q) / b
        where b = odds - 1, p = probability, q = 1 - p
        """
        if odds <= 1:
            return {'size': 0, 'kelly_fraction': 0, 'edge': 0}
        
        # Calculate expected edge
        b = odds - 1
        p = probability
        q = 1 - p
        
        expected_value = (p * b) - q
        edge = expected_value  # Edge as decimal
        
        # Kelly calculation
        kelly = max(0, (b * p - q) / b)
        
        # Apply fractional Kelly
        adjusted_kelly = kelly * self.fraction
        
        # Confidence adjustment
        adjusted_kelly *= confidence
        
        # Cap at maximum
        adjusted_kelly = min(adjusted_kelly, self.max_kelly)
        
        return {
            'kelly_fraction': adjusted_kelly,
            'edge': edge,
            'expected_value': expected_value,
            'raw_kelly': kelly,
            'confidence_adjusted': confidence
        }
    
    def size_position(self, bankroll: float, kelly_fraction: float, max_position: float) -> float:
        """Calculate position size"""
        # Calculate position size
        size = self.portfolio * size_frac
        size = min(size, max_position)
        size = max(size, 10)  # Minimum $10


class OrderFlowAnalyzer:
    """Analyze order book and predict short-term price movements"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=10)
    
    def analyze(self, market_id: str, token_id: str) -> Dict:
        """Analyze order book for imbalance"""
        try:
            # Get orderbook
            resp = self.client.get('https://clob.polymarket.com/book', params={'token_id': token_id})
            if resp.status_code != 200:
                return {'imbalance': 0.5, 'direction': 'neutral', 'confidence': 0}
            
            book = resp.json()
            bids = book.get('bids', [])
            asks = book.get('asks', [])
            
            # Calculate volumes
            bid_volume = sum(float(b.get('size', 0)) for b in bids[:5])
            ask_volume = sum(float(a.get('size', 0)) for a in asks[:5])
            
            total = bid_volume + ask_volume
            if total == 0:
                return {'imbalance': 0.5, 'direction': 'neutral', 'confidence': 0}
            
            # Imbalance ratio (0-1, 0.5 = balanced)
            imbalance = bid_volume / total
            
            # Predict direction (IR > 0.65 predicts UP in 15-30 min)
            direction = 'up' if imbalance > 0.65 else 'down' if imbalance < 0.35 else 'neutral'
            
            # Confidence based on imbalance strength
            confidence = abs(imbalance - 0.5) * 2  # 0 = uncertain, 1 = confident
            
            return {
                'imbalance': imbalance,
                'direction': direction,
                'confidence': confidence,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'spread': (float(asks[0].get('price', 0)) - float(bids[0].get('price', 0))) if bids and asks else 0
            }
        except:
            return {'imbalance': 0.5, 'direction': 'neutral', 'confidence': 0}
    
    def predict_short_term(self, imbalance: float) -> float:
        """Predict short-term price movement probability"""
        # Based on research: IR > 0.65 predicts price increase within 15-30 min (58% accuracy)
        if imbalance > 0.65:
            return 0.58
        elif imbalance < 0.35:
            return 0.42
        return 0.50


# ==================== TRADING STRATEGIES ====================

class StrategyEngine:
    """Multiple strategy implementation"""
    
    def __init__(self):
        self.prob_estimator = ProbabilityEstimator()
        self.kelly = KellyCriterion(fraction=0.25)
        self.order_flow = OrderFlowAnalyzer()
        self.gamma = PolymarketGammaClient()
    
    def analyze_opportunity(self, market: Any, news: List[Dict], price_history: List[float] = None) -> Dict:
        """Analyze a market opportunity using all strategies"""
        
        market_data = {
            'question': market.question,
            'price_yes': market.outcome_prices[0] if market.outcome_prices else 0.5,
            'price_no': market.outcome_prices[1] if market.outcome_prices and len(market.outcome_prices) > 1 else 0.5,
            'volume': market.volume_24hr or 0,
            'liquidity': market.liquidity or 0,
            'id': market.id,
            'condition_id': market.condition_id
        }
        
        # Get order flow data
        order_flow = {'imbalance': 0.5, 'direction': 'neutral', 'confidence': 0}
        if market.token_ids and len(market.token_ids) > 0:
            order_flow = self.order_flow.analyze(market.id, market.token_ids[0])
        
        # Calculate probability
        prob_result = self.prob_estimator.estimate(market_data, news, price_history or [])
        
        # Calculate odds (1 / price)
        price = market_data['price_yes']
        odds = 1 / price if price > 0 else 1
        
        # Kelly sizing
        kelly_result = self.kelly.calculate(prob_result['probability'], odds, prob_result['confidence'])
        
        # Determine best strategy
        strategy = self._select_strategy(market_data, order_flow, prob_result)
        
        # Calculate edge
        edge = prob_result['probability'] - price
        
        return {
            'market_id': market.id,
            'question': market.question,
            'market_price': price,
            'estimated_probability': prob_result['probability'],
            'confidence': prob_result['confidence'],
            'edge': edge,
            'strategy': strategy,
            'kelly_size': kelly_result['kelly_fraction'],
            'kelly_edge': kelly_result['edge'],
            'order_flow': order_flow,
            'components': prob_result['components'],
            'action': self._determine_action(edge, kelly_result, order_flow)
        }
    
    def _select_strategy(self, market_data: Dict, order_flow: Dict, prob: Dict) -> str:
        """Select best strategy based on conditions"""
        
        # Check for arbitrage (probability sums to > 1 or < 1)
        price_yes = market_data.get('price_yes', 0.5)
        price_no = market_data.get('price_no', 0.5)
        
        if price_yes + price_no > 1.02 or price_yes + price_no < 0.98:
            return 'ARBITRAGE'
        
        # Check for momentum (order flow imbalance)
        if abs(order_flow.get('imbalance', 0.5) - 0.5) > 0.15:
            return 'MOMENTUM'
        
        # Check for mean reversion (high confidence + edge)
        if prob['confidence'] > 0.7 and abs(prob['probability'] - market_data.get('price_yes', 0.5)) > 0.15:
            return 'MEAN_REVERSION'
        
        # Check for event-driven (news available)
        return 'FUNDAMENTAL'
    
    def _determine_action(self, edge: float, kelly: Dict, order_flow: Dict) -> Optional[Dict]:
        """Determine trading action based on all signals"""
        
        # Minimum edge threshold (5%)
        if abs(edge) < 0.05:
            return None
        
        # Minimum Kelly size ($5)
        if kelly['kelly_fraction'] < 0.005:
            return None
        
        # Check order flow direction alignment
        if order_flow['direction'] == 'up' and edge > 0:
            # Aligned - go ahead
            pass
        elif order_flow['direction'] == 'down' and edge < 0:
            # Aligned - go ahead
            pass
        elif order_flow['confidence'] > 0.5:
            # Strong order flow - trust it
            pass
        else:
            # Not aligned, require higher edge
            if abs(edge) < 0.10:
                return None
        
        action = 'BUY YES' if edge > 0 else 'SELL YES'
        
        return {
            'action': action,
            'edge': edge,
            'size_fraction': kelly['kelly_fraction'],
            'expected_value': kelly['expected_value']
        }


class StrategyDiscovery:
    """Discover and learn from winning strategies"""
    
    def __init__(self):
        self.strategies_file = 'D:/polymarket_ai_bot/strategies.json'
        self.load_strategies()
    
    def load_strategies(self):
        """Load historical strategies"""
        try:
            with open(self.strategies_file, 'r') as f:
                self.strategies = json.load(f)
        except:
            self.strategies = {
                'winning_patterns': [],
                'losing_patterns': [],
                'edge_thresholds': [],
                'category_performance': {}
            }
    
    def save_strategies(self):
        """Save strategies"""
        with open(self.strategies_file, 'w') as f:
            json.dump(self.strategies, f, indent=2)
    
    def record_result(self, trade: Dict, result: str):
        """Record trade result for learning"""
        
        pattern = {
            'strategy': trade.get('strategy', 'unknown'),
            'edge': trade.get('edge', 0),
            'confidence': trade.get('confidence', 0),
            'category': self._extract_category(trade.get('question', '')),
            'result': result
        }
        
        if result == 'WIN':
            self.strategies['winning_patterns'].append(pattern)
        else:
            self.strategies['losing_patterns'].append(pattern)
        
        # Keep last 100 patterns
        self.strategies['winning_patterns'] = self.strategies['winning_patterns'][-100:]
        self.strategies['losing_patterns'] = self.strategies['losing_patterns'][-100:]
        
        self.save_strategies()
    
    def _extract_category(self, question: str) -> str:
        """Extract category from question"""
        q = question.lower()
        if 'nhl' in q or 'stanley' in q:
            return 'sports_hockey'
        elif 'gta' in q:
            return 'gaming_gta'
        elif 'world cup' in q or 'fifa' in q:
            return 'sports_soccer'
        elif 'bitcoin' in q or 'btc' in q:
            return 'crypto'
        elif 'trump' in q or 'president' in q:
            return 'politics'
        return 'other'
    
    def get_best_parameters(self) -> Dict:
        """Learn best parameters from history"""
        
        # Analyze winning edge thresholds
        winning_edges = [p['edge'] for p in self.strategies['winning_patterns']]
        losing_edges = [p['edge'] for p in self.strategies['losing_patterns']]
        
        avg_win_edge = np.mean(winning_edges) if winning_edges else 0.10
        avg_loss_edge = np.mean(losing_edges) if losing_edges else 0.05
        
        # Category performance
        cat_wins = defaultdict(int)
        cat_total = defaultdict(int)
        
        for p in self.strategies['winning_patterns']:
            cat_wins[p['category']] += 1
            cat_total[p['category']] += 1
        for p in self.strategies['losing_patterns']:
            cat_total[p['category']] += 1
        
        cat_performance = {k: cat_wins[k] / cat_total[k] for k in cat_total}
        
        return {
            'min_edge_for_winning': avg_win_edge,
            'min_edge_threshold': max(0.05, avg_loss_edge),
            'best_categories': sorted(cat_performance.items(), key=lambda x: -x[1])[:3]
        }


# ==================== MAIN QUANT ENGINE ====================

class QuantTradingEngine:
    """Complete quantitative trading engine"""
    
    def __init__(self, portfolio=1000, max_position=100):
        self.gamma = PolymarketGammaClient()
        self.strategy_engine = StrategyEngine()
        self.strategy_discovery = StrategyDiscovery()
        self.client = httpx.Client(timeout=30)
        
        self.portfolio = portfolio
        self.max_position = max_position
        self.cycle_count = 0
        self.trades_executed = 0
        self.wins = 0
        self.losses = 0
        
    def scan_markets(self, min_volume=10000) -> List[Dict]:
        """Scan for trading opportunities"""
        
        # Get markets
        markets = self.gamma.get_markets(limit=100, closed=False)
        
        # Filter liquid markets
        liquid = [m for m in markets 
                  if m.volume_24hr and m.volume_24hr > min_volume
                  and m.liquidity and m.liquidity > 5000
                  and m.outcome_prices and len(m.outcome_prices) >= 2]
        
        liquid.sort(key=lambda x: x.volume_24hr, reverse=True)
        
        return liquid[:30]
    
    def analyze_market(self, market: Any) -> Dict:
        """Deep analysis of a single market"""
        
        # Get related news (simulated)
        search_terms = market.question.split()[:4]
        news = []  # Would integrate real news API
        
        # Analyze
        opportunity = self.strategy_engine.analyze_opportunity(market, news)
        
        return opportunity
    
    def execute_trade(self, opportunity: Dict) -> Dict:
        """Execute a trade with proper sizing"""
        
        action_data = opportunity.get('action')
        if not action_data:
            return None
        
        action = action_data['action']
        size_frac = action_data['size_fraction']
        price = opportunity['market_price']
        
        # Calculate size
        size = self.portfolio * size_frac
        size = min(size, self.max_position)
        size = max(size, 10)  # Minimum $10
        
        cost = size * price
        
        trade = {
            'id': str(uuid.uuid4())[:12],
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': action,
            'size': round(size, 2),
            'price': round(price, 4),
            'cost': round(cost, 2),
            'question': opportunity['question'],
            'edge': round(opportunity['edge'], 4),
            'confidence': round(opportunity['confidence'], 2),
            'strategy': opportunity['strategy'],
            'estimated_prob': round(opportunity['estimated_probability'], 3),
            'kelly_edge': round(action_data.get('kelly_edge', 0), 4),
            'result': 'PENDING'
        }
        
        self.trades_executed += 1
        
        return trade
    
    def run_cycle(self) -> Dict:
        """Run one complete trading cycle"""
        
        self.cycle_count += 1
        print(f"\n{'='*70}")
        print(f"QUANT CYCLE {self.cycle_count} | {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
        print(f"{'='*70}")
        
        # 1. Scan markets
        markets = self.scan_markets()
        print(f"[SCAN] {len(markets)} liquid markets")
        
        # 2. Analyze each
        opportunities = []
        for m in markets[:20]:
            opp = self.analyze_market(m)
            if opp.get('action') and opp['edge'] > 0.05:
                opportunities.append(opp)
        
        print(f"[ANALYSIS] {len(opportunities)} opportunities")
        
        # 3. Sort by edge
        opportunities.sort(key=lambda x: abs(x['edge']), reverse=True)
        
        # 4. Execute top opportunities
        trades = []
        for opp in opportunities[:5]:
            trade = self.execute_trade(opp)
            if trade:
                trades.append(trade)
                print(f"  {trade['action']} ${trade['size']:.0f} {opp['question'][:40]}...")
                print(f"    Edge: {opp['edge']*100:.1f}% | Conf: {opp['confidence']*100:.0f}% | {opp['strategy']}")
        
        # 5. Portfolio summary
        exposed = sum(t['cost'] for t in trades)
        cash = self.portfolio - exposed
        
        print(f"\n[PORTFOLIO] Total: ${self.portfolio} | Exposed: ${exposed:.0f} | Cash: ${cash:.0f}")
        print(f"[STATS] Trades: {self.trades_executed} | Wins: {self.wins} | Losses: {self.losses}")
        
        # Save state
        self._save_state(trades)
        
        return {'trades': trades, 'opportunities': len(opportunities)}
    
    def _save_state(self, trades: List[Dict]):
        """Save current state"""
        
        state = {
            'cycle': self.cycle_count,
            'trades': trades,
            'portfolio': self.portfolio,
            'trades_executed': self.trades_executed,
            'wins': self.wins,
            'losses': self.losses
        }
        
        with open('D:/polymarket_ai_bot/quant_state.json', 'w') as f:
            json.dump(state, f, indent=2)
    
    def run_continuous(self, cycles=None):
        """Run continuously"""
        
        print("\n" + "="*70)
        print("ADVANCED QUANT TRADING ENGINE")
        print("Strategies: Arbitrage | Momentum | Mean Reversion | Fundamental")
        print("="*70)
        
        while True:
            try:
                self.run_cycle()
                time.sleep(60)  # 60 second cycles
                
                if cycles and self.cycle_count >= cycles:
                    break
                    
            except KeyboardInterrupt:
                print("\n[STOP] Stopped")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(10)


if __name__ == "__main__":
    engine = QuantTradingEngine(portfolio=1000, max_position=100)
    engine.run_continuous(cycles=1000)