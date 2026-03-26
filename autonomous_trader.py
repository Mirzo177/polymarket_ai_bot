#!/usr/bin/env python3
"""
AUTONOMOUS TRADING AGENT - Paper Trading Mode
Runs continuously scanning markets and executing paper trades
"""
import os
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any

# Set up environment with builder credentials
os.environ['POLY_BUILDER_KEY'] = '019d2b2f-b867-7daf-ac0b-92da916743fd'
os.environ['POLY_BUILDER_SECRET'] = 'g8_tldos1eNeC1Ri6Itnaz49ibSBRCQKhYQCgK30qos='
os.environ['POLY_BUILDER_PASSPHRASE'] = 'bd017fc2ea140a60e42763d2383935fa6dd33b0d972ba08f7bf96d0c5cc41059'

from polymarket_apis import PolymarketGammaClient, PolymarketReadOnlyClobClient


class AutonomousTrader:
    """Self-improving autonomous trading agent"""
    
    def __init__(self, portfolio=1000, max_position=50, cycle_time=60):
        self.gamma = PolymarketGammaClient()
        self.clob = PolymarketReadOnlyClobClient()
        self.portfolio = portfolio
        self.max_position = max_position
        self.cycle_time = cycle_time
        self.trade_history = []
        self.wins = 0
        self.losses = 0
        self.cycle_count = 0
        
    def get_markets(self, min_volume=5000, min_liquidity=5000) -> List[Dict]:
        """Fetch liquid markets from Polymarket"""
        markets = self.gamma.get_markets(limit=100, closed=False)
        
        liquid = [m for m in markets 
                  if m.volume_24hr and m.volume_24hr > min_volume
                  and m.liquidity and m.liquidity > min_liquidity
                  and m.outcome_prices and len(m.outcome_prices) >= 2]
        
        liquid.sort(key=lambda x: x.volume_24hr, reverse=True)
        return liquid[:20]
    
    def analyze_market(self, market) -> Dict[str, Any]:
        """Analyze a single market for trading opportunities"""
        question = market.question
        price_yes = market.outcome_prices[0] if market.outcome_prices else 0.5
        price_no = market.outcome_prices[1] if len(market.outcome_prices) > 1 else 0.5
        volume = market.volume_24hr or 0
        liquidity = market.liquidity or 0
        end_date = market.end_date
        description = market.description or ""
        
        # My probability estimates (20+ year trader intuition)
        my_estimate = self._estimate_probability(question, description, price_yes)
        
        edge = price_yes - my_estimate
        
        return {
            'id': market.id,
            'question': question,
            'market_price': price_yes,
            'my_estimate': my_estimate,
            'edge': edge,
            'volume': volume,
            'liquidity': liquidity,
            'end_date': str(end_date) if end_date else 'Unknown',
            'description': description[:200]
        }
    
    def _estimate_probability(self, question: str, description: str, market_price: float) -> float:
        """Estimate true probability based on reasoning"""
        q = question.lower()
        
        # NHL Stanley Cup - markets at 0-1% are clearly wrong
        if 'stanley cup' in q or 'nhl' in q:
            teams_favorites = ['edmonton', 'vegas', 'toronto', 'boston', 'florida']
            teams_underdogs = ['washington', 'colorado', 'dallas', 'philadelphia', 'islanders', 'minnesota', 'new jersey']
            
            for fav in teams_favorites:
                if fav in q:
                    return 0.20  # Favorites have ~20% chance
            for ud in teams_underdogs:
                if ud in q:
                    return 0.08  # Underdogs ~8%
            return 0.10
        
        # GTA VI - very unlikely before June 2026
        if 'gta vi' in q or 'gta 6' in q:
            if 'june 2026' in q:
                return 0.03
            if '2025' in q:
                return 0.15
        
        # Jesus Christ return - essentially impossible
        if 'jesus christ return' in q or 'return before gta' in q:
            return 0.02
        
        # Sports - World Cup, qualifiers
        if 'world cup' in q or 'fifa' in q:
            if 'italy' in q:
                return 0.75
            if 'qualify' in q:
                return 0.60
        
        # BitBoy - legal case
        if 'bitboy' in q or 'convicted' in q:
            return 0.15
        
        # Crypto
        if 'bitcoin' in q or 'btc' in q:
            if '1m' in q:
                return 0.05
            return 0.50
        
        # Politics
        if 'trump' in q or 'president' in q:
            return 0.40
        
        # China/Taiwan
        if 'china' in q and 'taiwan' in q:
            return 0.15
        
        # Default to market price if no strong view
        return market_price
    
    def generate_trades(self, analysis: List[Dict]) -> List[Dict]:
        """Generate trade decisions from market analysis"""
        trades = []
        
        for m in analysis:
            edge = m['edge']
            price = m['market_price']
            volume = m['volume']
            
            # Only trade if edge > 5% and sufficient liquidity
            if abs(edge) > 0.05 and volume > 10000 and m['liquidity'] > 10000:
                # Position sizing - fractional Kelly
                size = abs(edge) * self.portfolio * 0.25
                size = min(size, self.max_position)
                
                if size < 5:  # Minimum size
                    continue
                
                action = 'BUY YES' if edge > 0 else 'SELL YES'
                
                trade = {
                    'id': str(uuid.uuid4())[:12],
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'action': action,
                    'size': round(size, 2),
                    'price': round(price, 4),
                    'cost': round(size * price, 2),
                    'question': m['question'],
                    'edge': round(abs(edge), 3),
                    'my_estimate': round(m['my_estimate'], 3),
                    'status': 'PAPER_EXECUTED'
                }
                trades.append(trade)
        
        return trades
    
    def execute_paper_trade(self, trade: Dict) -> Dict:
        """Simulate paper trade execution"""
        trade['executed_at'] = datetime.now(timezone.utc).isoformat()
        trade['result'] = 'PENDING'
        
        # Record trade
        self.trade_history.append(trade)
        
        return trade
    
    def run_cycle(self):
        """Run one trading cycle"""
        self.cycle_count += 1
        print(f"\n{'='*70}")
        print(f"CYCLE {self.cycle_count} | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*70}")
        
        # 1. Get markets
        markets = self.get_markets()
        print(f"[SCAN] Found {len(markets)} liquid markets")
        
        # 2. Analyze each market
        analysis = []
        for m in markets:
            a = self.analyze_market(m)
            analysis.append(a)
        
        # 3. Generate trades
        trades = self.generate_trades(analysis)
        print(f"[ANALYSIS] {len(analysis)} markets analyzed")
        print(f"[DECISION] {len(trades)} trades identified")
        
        # 4. Execute trades
        if trades:
            print(f"\n[EXECUTE] Executing {len(trades)} paper trades:")
            for t in trades:
                self.execute_paper_trade(t)
                print(f"  - {t['action']} ${t['size']:.2f} {t['question'][:45]}...")
                print(f"    Edge: {t['edge']*100:.1f}% | Cost: ${t['cost']:.2f}")
        
        # 5. Print portfolio summary
        total_exposed = sum(t['cost'] for t in self.trade_history)
        remaining = self.portfolio - total_exposed
        
        print(f"\n[PORTFOLIO] Total: ${self.portfolio:.2f} | Exposed: ${total_exposed:.2f} | Cash: ${remaining:.2f}")
        
        # 6. Log to file
        self._save_history()
        
        return len(trades)
    
    def _save_history(self):
        """Save trade history to file"""
        history = {
            'cycle_count': self.cycle_count,
            'total_trades': len(self.trade_history),
            'portfolio': self.portfolio,
            'trades': self.trade_history[-50:]  # Keep last 50
        }
        
        with open('D:/polymarket_ai_bot/trading_history.json', 'w') as f:
            json.dump(history, f, indent=2)
    
    def run_continuous(self, max_cycles=None):
        """Run trading cycles continuously"""
        print("\n" + "="*70)
        print("AUTONOMOUS TRADING AGENT - PAPER MODE")
        print("Starting continuous trading...")
        print("="*70)
        
        while True:
            try:
                trades = self.run_cycle()
                print(f"\n[SLEEP] Next cycle in {self.cycle_time} seconds...")
                time.sleep(self.cycle_time)
                
                if max_cycles and self.cycle_count >= max_cycles:
                    break
                    
            except KeyboardInterrupt:
                print("\n[STOP] Trading stopped by user")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(10)


if __name__ == "__main__":
    trader = AutonomousTrader(
        portfolio=1000,
        max_position=50,
        cycle_time=60
    )
    
    # Run 3 cycles for testing, then continuous
    trader.run_continuous(max_cycles=1000)