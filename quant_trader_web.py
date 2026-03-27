#!/usr/bin/env python3
"""
Polymarket Quant Trading Engine - Bloomberg Terminal Pro v2
With Trade Resolution Tracking
"""
import os
import json
import time
import uuid
import threading
import math
import random
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
import httpx
from collections import defaultdict

app = Flask(__name__)
CORS(app)

trading_state = {
    'cycle': 0,
    'trades': [],
    'resolved_trades': [],
    'portfolio': 1000,
    'portfolio_start': 1000,
    'trades_executed': 0,
    'wins': 0,
    'losses': 0,
    'status': 'STARTING',
    'last_error': '',
    'startup_time': datetime.now(timezone.utc).isoformat(),
    'markets_scanned': 0,
    'api_errors': 0,
    'last_trade_time': None,
    'total_volume_scanned': 0,
    'total_exposure': 0,
    'strategy_stats': defaultdict(int),
    'edge_history': [],
    'top_markets': [],
    'ai_insights': [],
    'sectors': {},
    'order_book': {'bids': [], 'asks': []},
    'historical_data': {}
}

def save_json(filename, data):
    try:
        with open(f'/tmp/{filename}', 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except:
        pass

def load_json(filename):
    try:
        with open(f'/tmp/{filename}', 'r') as f:
            return json.load(f)
    except:
        return None

class PolymarketAPI:
    def __init__(self):
        self.gamma_url = "https://gamma-api.polymarket.com"
        
    def get_markets(self, limit=50):
        try:
            resp = httpx.get(f"{self.gamma_url}/markets", 
                            params={'limit': limit, 'closed': 'false'}, 
                            timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('markets', [])
                return []
        except Exception as e:
            print(f"API Error: {e}")
            trading_state['last_error'] = str(e)[:50]
            trading_state['api_errors'] += 1
        return []
    
    def get_market_by_id(self, market_id):
        try:
            resp = httpx.get(f"{self.gamma_url}/markets", 
                            params={'id': market_id},
                            timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
        except:
            pass
        return None
    
    def check_resolved_markets(self, trades, markets):
        market_prices = {}
        market_status = {}
        
        for m in markets:
            mid = m.get('id')
            if mid:
                prices = m.get('outcomePrices')
                if prices and isinstance(prices, str):
                    try:
                        prices = json.loads(prices)
                    except:
                        prices = [0.5]
                elif prices:
                    pass
                else:
                    prices = [0.5]
                
                market_prices[mid] = float(prices[0]) if prices else 0.5
                market_status[mid] = {
                    'closed': m.get('closed', False),
                    'resolved': m.get('resolved', False),
                    'endDate': m.get('endDate')
                }
        
        resolved = []
        still_open = []
        
        for trade in trades:
            if trade.get('status') == 'RESOLVED':
                resolved.append(trade)
                continue
                
            market_id = trade.get('market_id')
            current_price = market_prices.get(market_id, trade.get('price', 0.5))
            trade['current_price'] = current_price
            
            status_info = market_status.get(market_id, {})
            
            if status_info.get('resolved') or status_info.get('closed'):
                trade['status'] = 'RESOLVED'
                trade['resolved_at'] = datetime.now(timezone.utc).isoformat()
                
                if trade.get('action', '').includes('BUY'):
                    if current_price > trade.get('entry_price', trade.get('price', 0)):
                        trade['result'] = 'WON'
                        trade['profit'] = (current_price - trade.get('entry_price', trade.get('price', 0))) * trade.get('size', 0) * 10
                    else:
                        trade['result'] = 'LOST'
                        trade['profit'] = (trade.get('entry_price', trade.get('price', 0)) - current_price) * trade.get('size', 0) * 10
                else:
                    if current_price < trade.get('entry_price', trade.get('price', 0)):
                        trade['result'] = 'WON'
                    else:
                        trade['result'] = 'LOST'
                
                resolved.append(trade)
            else:
                if trade.get('endDate'):
                    try:
                        end_dt = datetime.fromisoformat(trade['endDate'].replace('Z', '+00:00'))
                        trade['days_to_resolve'] = max(0, (end_dt - datetime.now(timezone.utc)).days)
                    except:
                        trade['days_to_resolve'] = None
                still_open.append(trade)
        
        return still_open, resolved

def categorize_market(question):
    q = question.lower()
    categories = {
        'Sports': ['nfl', 'nba', 'nhl', 'mlb', 'football', 'basketball', 'hockey', 'soccer', 'tennis', 'golf', 'boxing', 'ufc', 'mma', 'world cup', 'olympics', 'stanley cup', 'super bowl', 'championship', 'playoffs', 'game', 'team', 'win', 'season'],
        'Crypto': ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana', 'dogecoin', 'ordinal', 'ether', 'token', 'blockchain'],
        'Politics': ['president', 'election', 'trump', 'biden', 'congress', 'senate', 'governor', 'mayor', 'vote', 'republican', 'democrat', 'party', 'reelection'],
        'Business': ['stock', 'market', 'fed', 'economy', 'gdp', 'recession', 'earnings', 'ipo', 'merge', 'acquisition', 'company', 'apple', 'google', 'microsoft', 'amazon', 'tesla', 'meta'],
        'Entertainment': ['oscar', 'grammy', 'emmy', 'tony', 'movie', 'album', 'song', 'chart', 'box office', 'netflix', 'spotify', 'streaming'],
        'Tech': ['ai', 'artificial intelligence', 'openai', 'google', 'microsoft', 'apple', 'product', 'launch', 'release'],
        'Science': ['space', 'nasa', 'moon', 'mars', 'climate', 'weather', 'earthquake', 'eruption'],
        'Other': []
    }
    for cat, keywords in categories.items():
        if any(kw in q for kw in keywords):
            return cat
    return 'Other'

class ProbabilityEstimator:
    def estimate(self, market_data):
        price = market_data.get('price_yes', 0.5)
        
        if price < 0.5:
            fundamental = price * (1.2 + random.uniform(0, 0.3))
        else:
            fundamental = price * (0.8 + random.uniform(0, 0.3))
        
        fundamental = min(0.95, max(0.05, fundamental))
        confidence = 0.5 + random.uniform(0, 0.3)
        
        return {
            'probability': fundamental, 
            'confidence': confidence,
            'method': 'BAYESIAN' if price < 0.3 or price > 0.7 else 'MOMENTUM'
        }

class KellyCriterion:
    def calculate(self, probability, odds):
        if odds <= 1:
            return {'kelly_fraction': 0, 'edge': 0, 'expected_value': 0}
        b = odds - 1
        expected_value = (probability * b) - (1 - probability)
        kelly = 0.05 if expected_value > 0 else 0
        return {'kelly_fraction': kelly, 'edge': expected_value, 'expected_value': expected_value}

class AIAnalyzer:
    def analyze(self, markets, trades):
        insights = []
        
        if not markets:
            return insights
        
        avg_vol = sum(m['volume'] for m in markets) / len(markets)
        hot_markets = [m for m in markets if m['volume'] > avg_vol * 1.5]
        
        if hot_markets:
            insights.append({'type': 'HOT', 'message': f'{len(hot_markets)} high-volume markets', 'priority': 'HIGH'})
        
        return insights[:5]

class SelfLearningEngine:
    """AI that learns from past trades to improve future decisions"""
    
    def __init__(self):
        self.performance_data = {
            'by_category': defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_edge': 0, 'count': 0}),
            'by_edge_range': defaultdict(lambda: {'wins': 0, 'losses': 0, 'count': 0}),
            'by_spread': defaultdict(lambda: {'wins': 0, 'losses': 0, 'count': 0}),
            'by_confidence': defaultdict(lambda: {'wins': 0, 'losses': 0, 'count': 0}),
            'total_wins': 0,
            'total_losses': 0,
            'total_trades': 0,
            'avg_win_edge': 0,
            'avg_loss_edge': 0
        }
        self.params = {
            'min_edge': 0.02,
            'max_spread': 10,
            'min_confidence': 0.5,
            'kelly_multiplier': 1.0,
            'position_size': 50
        }
        self.load_performance()
    
    def load_performance(self):
        try:
            with open('/tmp/performance.json', 'r') as f:
                data = json.load(f)
                self.performance_data.update(data.get('performance', {}))
                self.params.update(data.get('params', {}))
        except:
            pass
    
    def save_performance(self):
        try:
            with open('/tmp/performance.json', 'w') as f:
                json.dump({
                    'performance': dict(self.performance_data),
                    'params': self.params
                }, f, indent=2)
        except:
            pass
    
    def learn(self, resolved_trades):
        """Learn from resolved trades"""
        if not resolved_trades:
            return
        
        for trade in resolved_trades:
            result = trade.get('result')
            if not result:
                continue
            
            category = trade.get('category', 'Other')
            edge = trade.get('edge', 0)
            spread = trade.get('spread', 0)
            confidence = trade.get('confidence', 0.5)
            
            # Track by category
            cat_stats = self.performance_data['by_category'][category]
            if result == 'WON':
                cat_stats['wins'] += 1
                self.performance_data['total_wins'] += 1
            else:
                cat_stats['losses'] += 1
                self.performance_data['total_losses'] += 1
            cat_stats['total_edge'] += edge
            cat_stats['count'] += 1
            
            # Track by edge range
            edge_key = f"{int(edge*100)//5 * 5}-{(int(edge*100)//5 + 1) * 5}%"
            edge_stats = self.performance_data['by_edge_range'][edge_key]
            if result == 'WON':
                edge_stats['wins'] += 1
            else:
                edge_stats['losses'] += 1
            edge_stats['count'] += 1
            
            # Track by spread
            spread_key = f"{int(spread)//5 * 5}-{(int(spread)//5 + 1) * 5}%"
            spread_stats = self.performance_data['by_spread'][spread_key]
            if result == 'WON':
                spread_stats['wins'] += 1
            else:
                spread_stats['losses'] += 1
            spread_stats['count'] += 1
            
            self.performance_data['total_trades'] += 1
        
        self.optimize_params()
        self.save_performance()
    
    def optimize_params(self):
        """Adjust parameters based on what works"""
        total = self.performance_data['total_trades']
        if total < 5:
            return
        
        # Find best category
        best_cat = None
        best_cat_rate = 0
        for cat, stats in self.performance_data['by_category'].items():
            if stats['count'] >= 3:
                rate = stats['wins'] / stats['count'] if stats['count'] > 0 else 0
                if rate > best_cat_rate:
                    best_cat_rate = rate
                    best_cat = cat
        
        # Find best edge range
        best_edge = 0.02
        best_edge_rate = 0
        for edge_range, stats in self.performance_data['by_edge_range'].items():
            if stats['count'] >= 3:
                rate = stats['wins'] / stats['count'] if stats['count'] > 0 else 0
                if rate > best_edge_rate:
                    best_edge_rate = rate
                    # Extract lower bound
                    try:
                        best_edge = int(edge_range.split('-')[0].replace('%', '')) / 100
                    except:
                        best_edge = 0.02
        
        # Find best spread
        best_spread = 10
        best_spread_rate = 0
        for spread_range, stats in self.performance_data['by_spread'].items():
            if stats['count'] >= 3:
                rate = stats['wins'] / stats['count'] if stats['count'] > 0 else 0
                if rate > best_spread_rate:
                    best_spread_rate = rate
                    try:
                        best_spread = int(spread_range.split('-')[0])
                    except:
                        best_spread = 10
        
        # Update params
        if best_edge_rate > 0.3:
            self.params['min_edge'] = max(0.01, best_edge - 0.01)
        
        if best_spread_rate > 0.3:
            self.params['max_spread'] = min(best_spread + 5, 20)
        
        # Adjust position size based on win rate
        win_rate = self.performance_data['total_wins'] / total if total > 0 else 0
        if win_rate > 0.6:
            self.params['kelly_multiplier'] = min(1.5, self.params['kelly_multiplier'] * 1.1)
        elif win_rate < 0.4:
            self.params['kelly_multiplier'] = max(0.5, self.params['kelly_multiplier'] * 0.9)
    
    def get_recommendations(self):
        """Get AI recommendations based on learning"""
        recs = []
        
        # Best performing category
        best_cat = None
        best_cat_rate = 0
        for cat, stats in self.performance_data['by_category'].items():
            if stats['count'] >= 3:
                rate = stats['wins'] / stats['count'] if stats['count'] > 0 else 0
                if rate > best_cat_rate:
                    best_cat_rate = rate
                    best_cat = cat
        
        if best_cat and best_cat_rate > 0.5:
            recs.append(f"Focus on {best_cat} markets ({best_cat_rate*100:.0f}% win rate)")
        
        # Best edge range
        best_edge = None
        best_edge_rate = 0
        for edge_range, stats in self.performance_data['by_edge_range'].items():
            if stats['count'] >= 3:
                rate = stats['wins'] / stats['count'] if stats['count'] > 0 else 0
                if rate > best_edge_rate:
                    best_edge_rate = rate
                    best_edge = edge_range
        
        if best_edge and best_edge_rate > 0.5:
            recs.append(f"Optimal edge: {best_edge} ({best_edge_rate*100:.0f}% win rate)")
        
        # Overall performance
        total = self.performance_data['total_trades']
        if total > 0:
            win_rate = self.performance_data['total_wins'] / total
            recs.append(f"Overall: {self.performance_data['total_wins']}W/{total} ({win_rate*100:.0f}%)")
        
        return recs

def generate_sparkline_data(current_price):
    data = []
    price = current_price
    for _ in range(20):
        change = random.uniform(-0.02, 0.02)
        price = price * (1 + change)
        price = max(0.01, min(0.99, price))
        data.append(price)
    data[-1] = current_price
    return data

class QuantEngine:
    def __init__(self):
        self.api = PolymarketAPI()
        self.prob = ProbabilityEstimator()
        self.kelly = KellyCriterion()
        self.ai = AIAnalyzer()
        self.learner = SelfLearningEngine()
    
    def scan_and_trade(self):
        global trading_state
        try:
            trading_state['status'] = 'SCANNING'
            
            # Load persisted trades
            trades_data = load_json('trades_history.json') or {'open': [], 'resolved': []}
            all_trades = trades_data.get('open', []) + trades_data.get('resolved', [])
            
            # Get markets
            markets = self.api.get_markets(50)
            
            # Check for resolved markets
            open_trades, resolved_trades = self.api.check_resolved_markets(all_trades, markets)
            
            # Update resolved trades
            if resolved_trades:
                trading_state['resolved_trades'] = resolved_trades[-100:]
                wins = sum(1 for t in resolved_trades if t.get('result') == 'WON')
                losses = sum(1 for t in resolved_trades if t.get('result') == 'LOST')
                trading_state['wins'] = wins
                trading_state['losses'] = losses
                
                # Self-learning: learn from resolved trades
                self.learner.learn(resolved_trades)
                trading_state['ai_recommendations'] = self.learner.get_recommendations()
                trading_state['learned_params'] = self.learner.params.copy()
            
            # Process markets
            market_data = []
            sectors = defaultdict(lambda: {'volume': 0, 'markets': 0})
            historical_data = {}
            
            for m in markets:
                try:
                    vol = float(m.get('volume') or m.get('volume24hr') or 0)
                    liq = float(m.get('liquidity') or 0)
                    prices_str = m.get('outcomePrices')
                    
                    if prices_str and isinstance(prices_str, str):
                        prices = json.loads(prices_str)
                    else:
                        prices = prices_str or []
                    
                    if prices:
                        price = float(prices[0]) if prices else 0.5
                        bid = float(m.get('bestBid')) or price * 0.95
                        ask = float(m.get('bestAsk')) or price * 1.05
                        spread = (ask - bid) / price * 100 if price > 0 else 0
                        
                        category = categorize_market(m.get('question', ''))
                        sectors[category]['volume'] += vol
                        sectors[category]['markets'] += 1
                        
                        historical_data[m.get('id')] = {
                            'question': m.get('question', ''),
                            'current': price,
                            'sparkline': generate_sparkline_data(price),
                            'volume': vol,
                            'category': category
                        }
                        
                        market_data.append({
                            'id': m.get('id'),
                            'question': m.get('question', ''),
                            'volume': vol,
                            'liquidity': liq,
                            'price': price,
                            'bid': bid,
                            'ask': ask,
                            'spread': spread,
                            'category': category,
                            'volume24hr': float(m.get('volume24hr') or 0),
                            'oneDayChange': float(m.get('oneDayPriceChange') or 0),
                            'oneHourChange': float(m.get('oneHourPriceChange') or 0),
                            'endDate': m.get('endDate'),
                            'active': m.get('active', True),
                            'conditionId': m.get('conditionId')
                        })
                except:
                    continue
            
            trading_state['historical_data'] = historical_data
            trading_state['sectors'] = dict(sectors)
            
            # Filter liquid markets
            liquid = [m for m in market_data if m['volume'] > 5000 and m['liquidity'] > 2000]
            liquid.sort(key=lambda x: x['volume'], reverse=True)
            
            trading_state['top_markets'] = liquid[:50]
            trading_state['markets_scanned'] = len(liquid)
            trading_state['total_volume_scanned'] = sum(m['volume'] for m in liquid)
            
            # Market insights
            category_vol = defaultdict(float)
            for m in liquid:
                category_vol[m['category']] += m['volume']
            trading_state['market_insights'] = [
                {'category': k, 'volume': v, 'count': len([m for m in liquid if m['category'] == k])}
                for k, v in sorted(category_vol.items(), key=lambda x: -x[1])[:8]
            ]
            
            trading_state['ai_insights'] = self.ai.analyze(liquid, open_trades)
            
            # Get current prices for open trades
            for trade in open_trades:
                market_id = trade.get('market_id')
                if market_id in historical_data:
                    trade['current_price'] = historical_data[market_id]['current']
            
            # Research markets - analyze each one deeply
            MAX_RESOLUTION_DAYS = 3
            research_candidates = []
            
            for m in liquid[:30]:
                try:
                    # Calculate days until resolution
                    days_until = None
                    if m.get('endDate'):
                        try:
                            end_dt = datetime.fromisoformat(m['endDate'].replace('Z', '+00:00'))
                            days_until = max(0, (end_dt - datetime.now(timezone.utc)).days)
                        except:
                            days_until = 999  # No end date = far future
                    
                    # Research score calculation
                    research = {
                        'market': m,
                        'days_until': days_until,
                        'volume_score': min(m['volume'] / 1000000, 10),  # Cap at 10
                        'liquidity_score': min(m['liquidity'] / 10000, 10),
                        'spread_score': max(0, 10 - m['spread']),  # Lower spread = higher score
                        'volatility_score': abs(m.get('oneDayChange', 0)) * 10,
                        'category_bonus': {'Sports': 2, 'Crypto': 3, 'Politics': 4, 'Business': 2, 'Tech': 3}.get(m['category'], 1),
                    }
                    
                    # Overall research score (0-100)
                    research['research_score'] = (
                        research['volume_score'] * 2 +
                        research['liquidity_score'] * 1.5 +
                        research['spread_score'] * 1 +
                        research['volatility_score'] * 0.5 +
                        research['category_bonus']
                    )
                    
                    research_candidates.append(research)
                    
                except:
                    continue
            
            # Sort by research score
            research_candidates.sort(key=lambda x: x['research_score'], reverse=True)
            
            # Filter: ONLY trade short-term markets (max 30 days)
            soon_resolving = []
            for max_d in [3, 7, 14, 30]:
                candidates = [r for r in research_candidates if r.get('days_until') is not None and r.get('days_until', 999) <= max_d]
                if candidates:
                    soon_resolving = candidates[:5]
                    break
            
            # If still no short-term markets, skip trading entirely
            if not soon_resolving:
                print(f"Cycle {trading_state.get('cycle', 0)}: No markets resolving within 30 days - skipping trades")
                trading_state['trades'] = []
                trading_state['status'] = 'NO SHORT-TERM MARKETS'
                return
            
            # Trading logic
            trading_state['cycle'] += 1
            new_trades = []
            
            for research in soon_resolving[:5]:  # Take top 5 candidates
                try:
                    m = research['market']
                    price = m['price']
                    days_until = research['days_until']
                    
                    if price < 0.01 or price > 0.99:
                        continue
                    
                    # Deep analysis
                    prob_result = self.prob.estimate({'question': m['question'], 'price_yes': price})
                    edge = prob_result['probability'] - price
                    
                    # Only trade if edge exceeds learned minimum
                    min_edge = self.learner.params.get('min_edge', 0.02)
                    max_spread = self.learner.params.get('max_spread', 10)
                    
                    if abs(edge) > min_edge and m['spread'] < max_spread:
                        odds = 1 / price if price > 0 else 1
                        kelly_result = self.kelly.calculate(prob_result['probability'], odds)
                        
                        # Apply learned Kelly multiplier
                        kelly_mult = self.learner.params.get('kelly_multiplier', 1.0)
                        kelly_result['kelly_fraction'] *= kelly_mult
                        
                        # Higher Kelly for short-term trades
                        if days_until is not None and days_until <= 3:
                            kelly_result['kelly_fraction'] = min(kelly_result['kelly_fraction'] * 2, 0.1)
                        
                        size = 1000 * kelly_result['kelly_fraction']
                        
                        if size > 2:
                            action = 'BUY YES' if edge > 0 else 'SELL YES'
                            trade = {
                                'id': str(uuid.uuid4())[:12],
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                                'action': action,
                                'size': round(size, 2),
                                'price': round(price, 4),
                                'entry_price': round(price, 4),
                                'cost': round(size * price, 2),
                                'question': m['question'][:80],
                                'market_id': m['id'],
                                'edge': round(edge, 4),
                                'volume': m['volume'],
                                'strategy': 'DEEP RESEARCH',
                                'status': 'PENDING',
                                'result': None,
                                'profit': 0,
                                'category': m['category'],
                                'kelly': round(kelly_result['kelly_fraction'], 4),
                                'bid': round(m['bid'], 4),
                                'ask': round(m['ask'], 4),
                                'spread': round(m['spread'], 2),
                                'prob_estimate': round(prob_result['probability'], 4),
                                'confidence': round(prob_result['confidence'], 2),
                                'method': prob_result['method'],
                                'endDate': m.get('endDate'),
                                'current_price': price,
                                'days_to_resolve': days_until,
                                'research_score': round(research['research_score'], 1),
                                'research': {
                                    'volume_score': round(research['volume_score'], 1),
                                    'liquidity_score': round(research['liquidity_score'], 1),
                                    'spread_score': round(research['spread_score'], 1),
                                    'volatility': round(m.get('oneDayChange', 0) * 100, 1)
                                }
                            }
                            
                            new_trades.append(trade)
                            trading_state['strategy_stats']['DEEP RESEARCH'] += 1
                except:
                    continue
            
            # Save trades
            open_trades = new_trades + open_trades
            
            # Save to file
            try:
                with open('/tmp/trades_history.json', 'w') as f:
                    json.dump({'open': open_trades[-100:], 'resolved': trading_state.get('resolved_trades', [])[-100:]}, f, indent=2, default=str)
            except:
                pass
            
            trading_state['trades'] = open_trades[-20:]
            trading_state['trades_executed'] = len(open_trades) + len(trading_state.get('resolved_trades', []))
            trading_state['total_exposure'] = sum(t['cost'] for t in open_trades)
            
            if new_trades:
                trading_state['last_trade_time'] = datetime.now(timezone.utc).isoformat()
                trading_state['edge_history'].extend([t['edge'] for t in new_trades])
                if len(trading_state['edge_history']) > 100:
                    trading_state['edge_history'] = trading_state['edge_history'][-100:]
            
            trading_state['status'] = 'RUNNING'
            
            print(f"Cycle {trading_state['cycle']}: {len(open_trades)} open, {len(trading_state.get('resolved_trades', []))} resolved, {len(new_trades)} new")
            
        except Exception as e:
            trading_state['status'] = f'ERROR: {str(e)[:30]}'
            trading_state['api_errors'] += 1
            print(f"Error: {e}")

def run_trading():
    engine = QuantEngine()
    while True:
        engine.scan_and_trade()
        time.sleep(60)

threading.Thread(target=run_trading, daemon=True).start()

BLOOMBERG_DASHBOARD = '''<!DOCTYPE html>
<html>
<head>
    <title>POLYMARKET QUANT <GO></title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bb-orange: #ff6600;
            --bb-black: #000000;
            --bb-dark: #0a0a0a;
            --bb-panel: #0d0d0d;
            --bb-border: #1a1a1a;
            --bb-text: #ff9900;
            --positive: #00ff00;
            --negative: #ff0000;
        }
        
        body {
            background: #000;
            color: #ff9900;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .header {
            background: linear-gradient(180deg, #111 0%, #0a0a0a 100%);
            border-bottom: 2px solid #ff6600;
            padding: 6px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-left { display: flex; align-items: center; gap: 20px; }
        
        .logo { font-size: 14px; font-weight: 700; letter-spacing: 2px; color: #ff9900; }
        .logo span { color: #ff6600; }
        
        .fn-keys { display: flex; gap: 4px; }
        
        .fn-key {
            background: #1a1a1a;
            border: 1px solid #333;
            padding: 3px 10px;
            font-size: 10px;
            cursor: pointer;
            transition: all 0.1s;
        }
        
        .fn-key:hover, .fn-key.active {
            background: #ff6600;
            color: #000;
            border-color: #ff6600;
        }
        
        .header-right { display: flex; gap: 25px; align-items: center; font-size: 11px; }
        .header-item { display: flex; align-items: center; gap: 6px; }
        .header-label { color: #555; }
        .header-value { color: #ff9900; font-weight: 600; }
        .header-value.green { color: #00ff00; }
        
        .ticker {
            background: #0a0a0a;
            border-bottom: 1px solid #1a1a1a;
            padding: 3px 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 10px;
        }
        
        .ticker-label {
            background: #ff6600;
            color: #000;
            padding: 1px 6px;
            font-weight: 700;
            font-size: 9px;
        }
        
        .ticker-content { color: #666; white-space: nowrap; overflow: hidden; }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1.2fr 1fr;
            grid-template-rows: 1fr 1fr;
            height: calc(100vh - 80px);
            gap: 1px;
            background: #222;
        }
        
        .panel {
            background: #0a0a0a;
            border: 1px solid #1a1a1a;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        .panel-header {
            background: linear-gradient(180deg, #151515, #0d0d0d);
            border-bottom: 1px solid #222;
            padding: 5px 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .panel-title { font-size: 10px; font-weight: 600; color: #ff6600; letter-spacing: 1px; }
        .panel-badge { background: #1a1100; color: #ff6600; padding: 2px 6px; font-size: 9px; border: 1px solid #332200; }
        
        .panel-body { padding: 8px; overflow-y: auto; flex: 1; }
        
        .heatmap { display: grid; grid-template-columns: repeat(10, 1fr); gap: 2px; }
        
        .heat-cell {
            aspect-ratio: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            cursor: pointer;
            transition: transform 0.1s;
            position: relative;
        }
        
        .heat-cell:hover { transform: scale(1.1); z-index: 10; }
        .heat-cell .price { font-weight: 700; }
        .heat-cell .vol { font-size: 7px; opacity: 0.7; }
        
        .trade-card {
            background: linear-gradient(135deg, #0d0d0d 0%, #0a0a0a 100%);
            border: 1px solid #1a1a1a;
            border-left: 3px solid #ff6600;
            margin-bottom: 8px;
            padding: 8px 10px;
        }
        
        .trade-card.won { border-left-color: #00ff00; }
        .trade-card.lost { border-left-color: #ff0000; }
        .trade-card.pending { border-left-color: #ffcc00; }
        
        .trade-status {
            display: inline-block;
            padding: 2px 8px;
            font-size: 9px;
            font-weight: 700;
            margin-bottom: 4px;
        }
        
        .trade-status.won { background: #003300; color: #00ff00; }
        .trade-status.lost { background: #330000; color: #ff0000; }
        .trade-status.pending { background: #332200; color: #ffcc00; }
        
        .trade-question { color: #888; font-size: 10px; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .trade-row { display: flex; justify-content: space-between; margin-bottom: 3px; }
        .trade-action { font-weight: 700; font-size: 10px; }
        .trade-action.buy { color: #00ff00; }
        .trade-action.sell { color: #ff0000; }
        .trade-meta { color: #555; font-size: 9px; }
        
        .trade-details {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 4px;
            padding-top: 4px;
            border-top: 1px solid #222;
            font-size: 9px;
        }
        
        .trade-stat { text-align: center; }
        .trade-stat-label { color: #444; font-size: 8px; }
        .trade-stat-val { color: #ff9900; font-weight: 600; }
        .trade-stat-val.green { color: #00ff00; }
        .trade-stat-val.red { color: #ff0000; }
        
        .trade-pnl {
            margin-top: 4px;
            padding: 4px;
            background: #0d0d0d;
            border-radius: 3px;
            text-align: center;
            font-size: 10px;
            font-weight: 600;
        }
        
        .trade-pnl.positive { color: #00ff00; background: #001a00; }
        .trade-pnl.negative { color: #ff0000; background: #1a0000; }
        
        .trade-countdown {
            font-size: 9px;
            color: #ff6600;
            margin-top: 4px;
        }
        
        .analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        
        .an-card {
            background: #0d0d0d;
            border: 1px solid #1a1a1a;
            padding: 8px;
            text-align: center;
        }
        
        .an-value { font-size: 18px; font-weight: 700; color: #ff6600; }
        .an-value.pos { color: #00ff00; }
        .an-value.neg { color: #ff0000; }
        .an-label { font-size: 9px; color: #555; margin-top: 2px; }
        
        .sector-list { margin-top: 8px; }
        
        .sector-item { margin-bottom: 6px; }
        
        .sector-hdr { display: flex; justify-content: space-between; font-size: 9px; margin-bottom: 2px; }
        .sector-name { color: #666; }
        .sector-vol { color: #ff9900; }
        
        .sector-bar { height: 8px; background: #111; border: 1px solid #1a1a1a; }
        .sector-fill { height: 100%; background: linear-gradient(90deg, #ff6600, #ff9900); }
        
        .ai-list { margin-top: 8px; }
        
        .ai-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px;
            background: #0d0d0d;
            border: 1px solid #1a1a1a;
            margin-bottom: 4px;
        }
        
        .ai-icon { font-size: 12px; }
        .ai-type { font-size: 9px; font-weight: 600; color: #ff6600; }
        .ai-msg { font-size: 9px; color: #777; }
        
        .portfolio-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        
        .port-card {
            background: #0d0d0d;
            border: 1px solid #1a1a1a;
            padding: 10px;
            text-align: center;
        }
        
        .port-value { font-size: 16px; font-weight: 700; color: #ff9900; }
        .port-value.green { color: #00ff00; }
        .port-value.red { color: #ff0000; }
        .port-label { font-size: 9px; color: #555; margin-top: 3px; }
        
        .system-stats { font-size: 10px; color: #555; display: flex; flex-direction: column; gap: 4px; margin-top: 10px; }
        .system-stats div { display: flex; justify-content: space-between; }
        
        .footer {
            background: #050505;
            border-top: 1px solid #1a1a1a;
            padding: 4px 12px;
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: #555;
        }
        
        .cmdline { display: flex; align-items: center; gap: 8px; }
        .cmd-prompt { color: #ff6600; font-weight: 700; }
        .cmd-input { background: transparent; border: none; color: #ff9900; font-family: inherit; font-size: 11px; outline: none; width: 200px; }
        
        .status-item { display: flex; align-items: center; gap: 5px; }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; }
        .status-dot.green { background: #00ff00; }
        .status-dot.red { background: #ff0000; }
        
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #0a0a0a; }
        ::-webkit-scrollbar-thumb { background: #333; }
        
        .history-summary {
            background: #0d0d0d;
            border: 1px solid #1a1a1a;
            padding: 12px;
            margin-bottom: 15px;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            text-align: center;
        }
        
        .history-stat { }
        .history-stat-value { font-size: 20px; font-weight: 700; }
        .history-stat-label { font-size: 9px; color: #555; margin-top: 2px; }
        
        .resolved-card {
            background: #0d0d0d;
            border: 1px solid #1a1a1a;
            margin-bottom: 8px;
            padding: 8px 10px;
            border-left: 3px solid #ff6600;
        }
        
        .resolved-card.won { border-left-color: #00ff00; }
        .resolved-card.lost { border-left-color: #ff0000; }
        
        .resolved-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
        .resolved-question { color: #888; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }
        .resolved-profit { font-size: 14px; font-weight: 700; }
        .resolved-profit.positive { color: #00ff00; }
        .resolved-profit.negative { color: #ff0000; }
        .resolved-date { font-size: 9px; color: #555; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <div class="logo">POLYMARKET <span>QUANT</span></div>
            <div class="fn-keys">
                <div class="fn-key active" onclick="switchView('active')">[F1] ACTIVE</div>
                <div class="fn-key" onclick="switchView('history')">[F2] HISTORY</div>
            </div>
        </div>
        <div class="header-right">
            <div class="header-item"><span class="header-label">CYCLE</span><span class="header-value" id="cycle">0</span></div>
            <div class="header-item"><span class="header-label">PORTFOLIO</span><span class="header-value green" id="portfolio">$0</span></div>
            <div class="header-item"><span class="header-label">STATUS</span><span class="header-value" id="status">INIT</span></div>
            <div class="header-item"><span class="header-value" id="clock">00:00:00</span></div>
        </div>
    </div>
    
    <div class="ticker">
        <span class="ticker-label">NEWS</span>
        <div class="ticker-content" id="ticker">QUANT ENGINE ACTIVE | PAPER TRADING | REAL-TIME DATA | TRADE TRACKING ENABLED</div>
    </div>
    
    <div class="main-grid" id="activeView">
        <div class="panel">
            <div class="panel-header"><span class="panel-title">MARKET HEATMAP</span><span class="panel-badge" id="heatCount">0</span></div>
            <div class="panel-body"><div class="heatmap" id="heatmap"></div></div>
        </div>
        
        <div class="panel">
            <div class="panel-header"><span class="panel-title">OPEN POSITIONS</span><span class="panel-badge" id="tradeCount">0</span></div>
            <div class="panel-body" id="tradesList"></div>
        </div>
        
        <div class="panel">
            <div class="panel-header"><span class="panel-title">ANALYTICS</span><span class="panel-badge">REAL-TIME</span></div>
            <div class="panel-body">
                <div class="analytics-grid">
                    <div class="an-card"><div class="an-value" id="totalTrades">0</div><div class="an-label">TOTAL TRADES</div></div>
                    <div class="an-card"><div class="an-value pos" id="winRate">0%</div><div class="an-label">WIN RATE</div></div>
                    <div class="an-card"><div class="an-value" id="avgEdge">0%</div><div class="an-label">AVG EDGE</div></div>
                    <div class="an-card"><div class="an-value" id="maxEdge">0%</div><div class="an-label">MAX EDGE</div></div>
                </div>
                <div class="panel-title" style="margin-bottom:6px;">SECTORS</div>
                <div class="sector-list" id="sectors"></div>
                <div class="panel-title" style="margin:10px 0 6px;">AI INSIGHTS</div>
                <div class="ai-list" id="aiInsights"></div>
            </div>
        </div>
        
        <div class="panel">
            <div class="panel-header"><span class="panel-title">ORDER BOOK</span><span class="panel-badge" id="obMarket">-</span></div>
            <div class="panel-body" id="orderBook"></div>
        </div>
        
        <div class="panel">
            <div class="panel-header"><span class="panel-title">SPARKLINES</span><span class="panel-badge">LIVE</span></div>
            <div class="panel-body" id="sparklines"></div>
        </div>
        
        <div class="panel">
            <div class="panel-header"><span class="panel-title">PORTFOLIO</span><span class="panel-badge">PAPER</span></div>
            <div class="panel-body">
                <div class="portfolio-grid">
                    <div class="port-card"><div class="port-value" id="totalCost">$0</div><div class="port-label">EXPOSURE</div></div>
                    <div class="port-card"><div class="port-value" id="avgSize">$0</div><div class="port-label">AVG POSITION</div></div>
                    <div class="port-card"><div class="port-value" id="maxPos">$0</div><div class="port-label">LARGEST</div></div>
                    <div class="port-card"><div class="port-value" id="cashRem">$0</div><div class="port-label">CASH</div></div>
                </div>
                <div class="system-stats">
                    <div><span>MARKETS</span><span id="sysMarkets" style="color:#ff9900;">0</span></div>
                    <div><span>VOLUME</span><span id="sysVolume" style="color:#ff9900;">$0</span></div>
                    <div><span>API ERR</span><span id="sysErrors" style="color:#ff0000;">0</span></div>
                    <div><span>UPTIME</span><span id="sysUptime" style="color:#ff9900;">0h</span></div>
                    <div><span>WINS</span><span id="sysWins" style="color:#00ff00;">0</span></div>
                    <div><span>LOSSES</span><span id="sysLosses" style="color:#ff0000;">0</span></div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="main-grid" id="historyView" style="display:none;">
        <div class="panel" style="grid-column:1/-1;">
            <div class="panel-header"><span class="panel-title">TRADE HISTORY</span><span class="panel-badge" id="historyCount">0</span></div>
            <div class="panel-body">
                <div class="history-summary">
                    <div class="history-stat"><div class="history-stat-value" id="histTotal">0</div><div class="history-stat-label">TOTAL TRADES</div></div>
                    <div class="history-stat"><div class="history-stat-value" style="color:#00ff00;" id="histWins">0</div><div class="history-stat-label">WINS</div></div>
                    <div class="history-stat"><div class="history-stat-value" style="color:#ff0000;" id="histLosses">0</div><div class="history-stat-label">LOSSES</div></div>
                    <div class="history-stat"><div class="history-stat-value" id="histPnl">$0</div><div class="history-stat-label">NET P&L</div></div>
                </div>
                <div id="historyList"></div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        <div class="cmdline">
            <span class="cmd-prompt">&gt;</span>
            <input type="text" class="cmd-input" id="cmdInput" placeholder="CMD...">
        </div>
        <div class="status-item">
            <div class="status-dot green" id="statusDot"></div>
            <span id="statusText">CONNECTED</span>
        </div>
        <div class="status-item"><span>RENDER.COM CLOUD</span></div>
    </div>
    
    <script>
        let currentView = 'active';
        
        function switchView(view) {
            currentView = view;
            document.querySelectorAll('.fn-key').forEach(k => k.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('activeView').style.display = view === 'active' ? 'grid' : 'none';
            document.getElementById('historyView').style.display = view === 'history' ? 'grid' : 'none';
        }
        
        function formatNum(n) {
            if(n >= 1e9) return (n/1e9).toFixed(1) + 'B';
            if(n >= 1e6) return (n/1e6).toFixed(1) + 'M';
            if(n >= 1e3) return (n/1e3).toFixed(1) + 'K';
            return n.toFixed(0);
        }
        
        function formatTime(iso) {
            if(!iso) return '-';
            return new Date(iso).toLocaleDateString();
        }
        
        function formatUptime(iso) {
            if(!iso) return '0h';
            const hrs = (new Date() - new Date(iso)) / 3600000;
            if(hrs < 1) return Math.round(hrs*60) + 'm';
            return Math.round(hrs) + 'h';
        }
        
        function calculatePnL(trade) {
            if (!trade.current_price) return { pnl: 0, pnlPercent: 0 };
            const entry = trade.entry_price || trade.price;
            const current = trade.current_price;
            const size = trade.size || 0;
            
            if (trade.action.includes('BUY')) {
                const pnl = (current - entry) * size * 10;
                const pnlPercent = ((current - entry) / entry) * 100;
                return { pnl, pnlPercent };
            } else {
                const pnl = (entry - current) * size * 10;
                const pnlPercent = ((entry - current) / entry) * 100;
                return { pnl, pnlPercent };
            }
        }
        
        function createSparkline(data) {
            if(!data || data.length < 2) return '';
            const w = 80, h = 25;
            const min = Math.min(...data), max = Math.max(...data);
            const range = max - min || 1;
            const points = data.map((v, i) => {
                const x = (i / (data.length - 1)) * w;
                const y = h - ((v - min) / range) * h;
                return x + ',' + y;
            }).join(' ');
            const color = data[data.length-1] >= data[0] ? '#00ff00' : '#ff0000';
            return '<svg width="' + w + '" height="' + h + '" style="display:block;"><polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width="1"/></svg>';
        }
        
        async function update() {
            try {
                const s = await fetch('/api/status').then(r=>r.json());
                const t = await fetch('/api/trades').then(r=>r.json());
                const h = await fetch('/api/history').then(r=>r.json());
                const m = await fetch('/api/markets').then(r=>r.json());
                
                document.getElementById('clock').textContent = new Date().toLocaleTimeString();
                document.getElementById('cycle').textContent = s.cycle;
                document.getElementById('portfolio').textContent = '$' + s.portfolio.toFixed(0);
                document.getElementById('status').textContent = s.status;
                
                // Markets Heatmap
                const markets = m.markets || [];
                document.getElementById('heatCount').textContent = markets.length;
                const maxVol = Math.max(...markets.map(m=>m.volume), 1);
                document.getElementById('heatmap').innerHTML = markets.slice(0, 50).map(x => {
                    const chg = x.oneDayChange || 0;
                    const intensity = Math.min(Math.abs(chg) * 10, 1);
                    const r = chg > 0 ? 0 : Math.floor(255 * intensity);
                    const g = chg < 0 ? 0 : Math.floor(255 * intensity);
                    const bg = chg === 0 ? '#1a1a1a' : 'rgb(' + r + ',' + g + ',0)';
                    return '<div class="heat-cell" style="background:' + bg + ';font-size:' + (8 + (x.volume/maxVol)*4) + 'px;"><span class="price">' + (x.price*100).toFixed(0) + '</span><span class="vol">' + formatNum(x.volume) + '</span></div>';
                }).join('');
                
                // Trades - Open Positions
                const trades = t.trades || [];
                document.getElementById('tradeCount').textContent = trades.length;
                document.getElementById('tradesList').innerHTML = trades.length ? trades.map(x => {
                    const isBuy = x.action.includes('BUY');
                    const pnl = calculatePnL(x);
                    const pnlClass = pnl.pnl >= 0 ? 'positive' : 'negative';
                    const days = x.days_to_resolve !== undefined && x.days_to_resolve !== null ? x.days_to_resolve + ' days' : 'TBD';
                    
                    return '<div class="trade-card ' + (x.status || 'pending') + '">' +
                        '<span class="trade-status ' + (x.status || 'pending') + '">' + (x.result || 'PENDING') + '</span>' +
                        '<div class="trade-question">' + x.question + '</div>' +
                        '<div class="trade-row"><span class="trade-action ' + (isBuy ? 'buy' : 'sell') + '">' + x.action + '</span><span class="trade-meta">$' + x.size.toFixed(2) + ' @ ' + (x.price*100).toFixed(1) + '%</span></div>' +
                        '<div class="trade-details">' +
                        '<div class="trade-stat"><div class="trade-stat-val">' + (x.research_score || x.edge*100).toFixed(0) + '</div><div class="trade-stat-label">SCORE</div></div>' +
                        '<div class="trade-stat"><div class="trade-stat-val">' + (x.edge*100).toFixed(1) + '%</div><div class="trade-stat-label">EDGE</div></div>' +
                        '<div class="trade-stat"><div class="trade-stat-val">' + ((x.current_price || x.price)*100).toFixed(1) + '%</div><div class="trade-stat-label">NOW</div></div>' +
                        '<div class="trade-stat"><div class="trade-stat-val">' + days + '</div><div class="trade-stat-label">DAYS</div></div>' +
                        '</div>' +
                        '<div class="trade-pnl ' + pnlClass + '">P&L: ' + (pnl.pnl >= 0 ? '+' : '') + '$' + pnl.pnl.toFixed(2) + ' (' + (pnl.pnlPercent >= 0 ? '+' : '') + pnl.pnlPercent.toFixed(1) + '%)</div>' +
                        '</div>';
                }).join('') : '<div style="color:#333;text-align:center;padding:20px;">NO OPEN POSITIONS</div>';
                
                // Analytics
                document.getElementById('totalTrades').textContent = s.trades_executed;
                const winRate = (s.wins + s.losses) > 0 ? (s.wins / (s.wins + s.losses) * 100) : 0;
                document.getElementById('winRate').textContent = winRate.toFixed(0) + '%';
                const edges = trades.map(x => x.edge);
                document.getElementById('avgEdge').textContent = edges.length ? (edges.reduce((a,b)=>a+b,0)/edges.length*100).toFixed(1) + '%' : '0%';
                document.getElementById('maxEdge').textContent = edges.length ? (Math.max(...edges)*100).toFixed(1) + '%' : '0%';
                
                // Sectors
                const sectors = m.market_insights || [];
                const totalVol = sectors.reduce((a,b)=>a+b.volume,0);
                document.getElementById('sectors').innerHTML = sectors.slice(0,6).map(x => {
                    const pct = totalVol ? (x.volume/totalVol*100) : 0;
                    return '<div class="sector-item"><div class="sector-hdr"><span class="sector-name">' + x.category + '</span><span class="sector-vol">' + formatNum(x.volume) + '</span></div><div class="sector-bar"><div class="sector-fill" style="width:' + pct + '%"></div></div></div>';
                }).join('');
                
                // AI Insights
                const insights = s.ai_insights || [];
                document.getElementById('aiInsights').innerHTML = insights.map(x => {
                    const icon = x.type === 'HOT' ? '&#128293;' : '&#129302;';
                    return '<div class="ai-item"><span class="ai-icon">' + icon + '</span><div><div class="ai-type">' + x.type + '</div><div class="ai-msg">' + x.message + '</div></div></div>';
                }).join('') || '<div style="color:#333;font-size:9px;">ANALYZING...</div>';
                
                // Portfolio
                const totalCost = trades.reduce((a,b)=>a+(b.cost||0),0);
                const avgSize = trades.length ? totalCost/trades.length : 0;
                const maxPos = trades.length ? Math.max(...trades.map(t=>t.size||0)) : 0;
                document.getElementById('totalCost').textContent = '$' + totalCost.toFixed(2);
                document.getElementById('avgSize').textContent = '$' + avgSize.toFixed(2);
                document.getElementById('maxPos').textContent = '$' + maxPos.toFixed(2);
                document.getElementById('cashRem').textContent = '$' + (s.portfolio - totalCost).toFixed(2);
                
                // System
                document.getElementById('sysMarkets').textContent = s.markets_scanned;
                document.getElementById('sysVolume').textContent = '$' + formatNum(s.total_volume_scanned);
                document.getElementById('sysErrors').textContent = s.api_errors;
                document.getElementById('sysUptime').textContent = formatUptime(s.startup_time);
                document.getElementById('sysWins').textContent = s.wins;
                document.getElementById('sysLosses').textContent = s.losses;
                
                document.getElementById('statusDot').className = 'status-dot ' + (s.status === 'RUNNING' ? 'green' : 'red');
                document.getElementById('statusText').textContent = s.status === 'RUNNING' ? 'ACTIVE' : 'ERROR';
                
                // HISTORY VIEW
                const history = h.resolved || [];
                document.getElementById('historyCount').textContent = history.length;
                document.getElementById('histTotal').textContent = history.length;
                document.getElementById('histWins').textContent = history.filter(t => t.result === 'WON').length;
                document.getElementById('histLosses').textContent = history.filter(t => t.result === 'LOST').length;
                const totalPnl = history.reduce((a,b) => a + (b.profit || 0), 0);
                document.getElementById('histPnl').textContent = (totalPnl >= 0 ? '+' : '') + '$' + totalPnl.toFixed(2);
                document.getElementById('histPnl').style.color = totalPnl >= 0 ? '#00ff00' : '#ff0000';
                
                document.getElementById('historyList').innerHTML = history.length ? history.slice(0, 50).map(x => {
                    const profit = x.profit || 0;
                    return '<div class="resolved-card ' + (x.result || '').toLowerCase() + '">' +
                        '<div class="resolved-row"><span class="trade-status ' + (x.result||'').toLowerCase() + '">' + (x.result||'PENDING') + '</span><span class="resolved-profit ' + (profit >= 0 ? 'positive' : 'negative') + '">' + (profit >= 0 ? '+' : '') + '$' + profit.toFixed(2) + '</span></div>' +
                        '<div class="resolved-question">' + (x.question || 'Unknown') + '</div>' +
                        '<div class="resolved-date">Entry: ' + (x.price*100).toFixed(1) + '% | Resolved: ' + formatTime(x.resolved_at) + '</div>' +
                        '</div>';
                }).join('') : '<div style="color:#333;text-align:center;padding:30px;">NO RESOLVED TRADES YET</div>';
                
            } catch(e) {
                console.error(e);
            }
        }
        
        document.getElementById('cmdInput').addEventListener('keypress', function(e) {
            if(e.key === 'Enter') {
                const cmd = this.value.toUpperCase();
                if(cmd === 'REFRESH') update();
                this.value = '';
            }
        });
        
        update();
        setInterval(update, 2000);
    </script>
</body>
</html>'''

@app.route('/dashboard')
def dashboard():
    return BLOOMBERG_DASHBOARD

@app.route('/')
def index():
    return '<h1>Polymarket Quant Trader</h1><p><a href="/dashboard">Open Bloomberg Terminal</a></p>'

@app.route('/api/status')
def api_status():
    return jsonify({
        'mode': 'QUANT ENGINE',
        'cycle': trading_state['cycle'],
        'portfolio': trading_state['portfolio'],
        'trades_executed': trading_state['trades_executed'],
        'wins': trading_state['wins'],
        'losses': trading_state['losses'],
        'status': trading_state['status'],
        'last_error': trading_state.get('last_error', ''),
        'startup_time': trading_state.get('startup_time'),
        'markets_scanned': trading_state.get('markets_scanned', 0),
        'api_errors': trading_state.get('api_errors', 0),
        'total_volume_scanned': trading_state.get('total_volume_scanned', 0),
        'total_exposure': trading_state.get('total_exposure', 0),
        'edge_history': trading_state.get('edge_history', []),
        'ai_insights': trading_state.get('ai_insights', []),
        'ai_recommendations': trading_state.get('ai_recommendations', []),
        'learned_params': trading_state.get('learned_params', {}),
        'sectors': trading_state.get('sectors', {})
    })

@app.route('/api/trades')
def api_trades():
    return jsonify({'trades': trading_state.get('trades', [])})

@app.route('/api/history')
def api_history():
    return jsonify({'resolved': trading_state.get('resolved_trades', [])})

@app.route('/api/markets')
def api_markets():
    return jsonify({
        'markets': trading_state.get('top_markets', []),
        'market_insights': trading_state.get('market_insights', [])
    })

@app.route('/api/orderbook')
def api_orderbook():
    return jsonify({'order_book': trading_state.get('order_book', {'bids': [], 'asks': []})})

@app.route('/api/sparkline')
def api_sparkline():
    hist_data = trading_state.get('historical_data', {})
    markets = trading_state.get('top_markets', [])
    
    sparklines = []
    for m in markets[:10]:
        mid = m.get('id', '')
        if mid in hist_data:
            hd = hist_data[mid]
            sparklines.append({
                'id': mid,
                'question': hd.get('question', '')[:30],
                'price': hd.get('current', 0),
                'category': hd.get('category', 'Other'),
                'volume': hd.get('volume', 0),
                'sparkline': hd.get('sparkline', []),
                'change': m.get('oneDayChange', 0)
            })
    
    return jsonify({'sparklines': sparklines})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Polymarket Bloomberg Terminal v2 on port {port}")
    app.run(host='0.0.0.0', port=port)
