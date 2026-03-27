#!/usr/bin/env python3
"""
Polymarket Quant Trading Engine - Bloomberg Terminal Edition
"""
import os
import json
import time
import uuid
import threading
import math
from datetime import datetime, timezone
from flask import Flask, jsonify
from flask_cors import CORS
import httpx
from collections import defaultdict

app = Flask(__name__)
CORS(app)

trading_state = {
    'cycle': 0,
    'trades': [],
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
    'strategy_stats': defaultdict(int),
    'edge_history': [],
    'pending_positions': [],
    'market_insights': [],
    'top_markets': [],
    'price_alerts': [],
    'ai_insights': [],
    'sectors': defaultdict(lambda: {'volume': 0, 'markets': 0, 'avg_price': 0}),
    'order_book': {'bids': [], 'asks': []},
    'news_feed': [],
    'historical_prices': []
}

def save_json(filename, data):
    try:
        with open(f'/tmp/{filename}', 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except:
        pass

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
    
    def get_market_order_book(self, condition_id):
        try:
            resp = httpx.get(f"{self.gamma_url}/orderbook", 
                            params={'conditionId': condition_id},
                            timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return None

def categorize_market(question):
    q = question.lower()
    categories = {
        'Sports': ['nfl', 'nba', 'nhl', 'mlb', 'football', 'basketball', 'hockey', 'soccer', 'tennis', 'golf', 'boxing', 'ufc', 'mma', 'world cup', 'olympics', 'stanley cup', 'super bowl', 'championship', 'playoffs', 'game', 'team', 'win', 'season'],
        'Crypto': ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana', 'dogecoin', 'ordinal', 'ether', 'token', 'blockchain', 'coin', '交易所'],
        'Politics': ['president', 'election', 'trump', 'biden', 'congress', 'senate', 'governor', 'mayor', 'vote', 'republican', 'democrat', 'party', 'reelection', 'minister', 'parliament', 'ukraine', 'russia', 'china'],
        'Business': ['stock', 'market', 'fed', 'economy', 'gdp', 'recession', 'earnings', 'ipo', 'merge', 'acquisition', 'company', 'apple', 'google', 'microsoft', 'amazon', 'tesla', 'meta', 'federal', 'interest rate'],
        'Entertainment': ['oscar', 'grammy', 'emmy', 'tony', 'movie', 'album', 'song', 'chart', 'box office', 'netflix', 'spotify', 'streaming', 'billboard', 'chart'],
        'Tech': ['ai', 'artificial intelligence', 'openai', 'google', 'microsoft', 'apple', 'product', 'launch', 'release', 'announce', 'tech', 'software', 'apple', 'meta'],
        'Science': ['space', 'nasa', 'moon', 'mars', 'climate', 'weather', 'earthquake', 'eruption', 'science', 'research', 'discovery'],
        'Other': []
    }
    for cat, keywords in categories.items():
        if any(kw in q for kw in keywords):
            return cat
    return 'Other'

class ProbabilityEstimator:
    def estimate(self, market_data):
        import random
        price = market_data.get('price_yes', 0.5)
        q = market_data.get('question', '').lower()
        
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
            insights.append({
                'type': 'HOT',
                'message': f'{len(hot_markets)} high-volume markets detected',
                'priority': 'HIGH'
            })
        
        price_ranges = {'low': 0, 'mid': 0, 'high': 0}
        for m in markets:
            if m['price'] < 0.2:
                price_ranges['low'] += 1
            elif m['price'] < 0.6:
                price_ranges['mid'] += 1
            else:
                price_ranges['high'] += 1
        
        if price_ranges['low'] > price_ranges['high']:
            insights.append({
                'type': 'BIAS',
                'message': 'Market bias: More underdogs priced in',
                'priority': 'MEDIUM'
            })
        
        if trades:
            avg_edge = sum(t['edge'] for t in trades) / len(trades)
            if avg_edge > 0.05:
                insights.append({
                    'type': 'EDGE',
                    'message': f'Strong edge detected: {avg_edge*100:.1f}% avg',
                    'priority': 'HIGH'
                })
        
        return insights[:5]

class QuantEngine:
    def __init__(self):
        self.api = PolymarketAPI()
        self.prob = ProbabilityEstimator()
        self.kelly = KellyCriterion()
        self.ai = AIAnalyzer()
    
    def scan_and_trade(self):
        global trading_state
        try:
            trading_state['status'] = 'SCANNING'
            markets = self.api.get_markets(50)
            
            market_data = []
            sectors = defaultdict(lambda: {'volume': 0, 'markets': 0, 'prices': []})
            
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
                        sectors[category]['prices'].append(price)
                        
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
                            'volume1wk': float(m.get('volume1wk') or 0),
                            'oneDayChange': float(m.get('oneDayPriceChange') or 0),
                            'oneHourChange': float(m.get('oneHourPriceChange') or 0),
                            'oneWeekChange': float(m.get('oneWeekPriceChange') or 0),
                            'endDate': m.get('endDate'),
                            'active': m.get('active', True),
                            'conditionId': m.get('conditionId')
                        })
                except:
                    continue
            
            # Update sectors
            trading_state['sectors'] = dict(sectors)
            
            # Filter liquid markets
            liquid = [m for m in market_data if m['volume'] > 5000 and m['liquidity'] > 2000]
            liquid.sort(key=lambda x: x['volume'], reverse=True)
            
            trading_state['top_markets'] = liquid[:20]
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
            
            # AI Analysis
            trading_state['ai_insights'] = self.ai.analyze(liquid, trading_state.get('trades', []))
            
            # Trading logic
            trading_state['cycle'] += 1
            new_trades = []
            
            for m in liquid[:15]:
                try:
                    price = m['price']
                    
                    if price < 0.01 or price > 0.99:
                        continue
                    
                    prob_result = self.prob.estimate({
                        'question': m['question'], 
                        'price_yes': price
                    })
                    edge = prob_result['probability'] - price
                    
                    if abs(edge) > 0.01:
                        odds = 1 / price if price > 0 else 1
                        kelly_result = self.kelly.calculate(prob_result['probability'], odds)
                        size = 1000 * kelly_result['kelly_fraction']
                        
                        if size > 2:
                            action = 'BUY YES' if edge > 0 else 'SELL YES'
                            trade = {
                                'id': str(uuid.uuid4())[:12],
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                                'action': action,
                                'size': round(size, 2),
                                'price': round(price, 4),
                                'cost': round(size * price, 2),
                                'question': m['question'][:60],
                                'edge': round(edge, 4),
                                'volume': m['volume'],
                                'strategy': 'FUNDAMENTAL',
                                'result': 'PENDING',
                                'category': m['category'],
                                'kelly': round(kelly_result['kelly_fraction'], 4),
                                'bid': round(m['bid'], 4),
                                'ask': round(m['ask'], 4),
                                'spread': round(m['spread'], 2),
                                'prob_estimate': round(prob_result['probability'], 4),
                                'confidence': round(prob_result['confidence'], 2),
                                'method': prob_result['method']
                            }
                            new_trades.append(trade)
                            trading_state['strategy_stats']['FUNDAMENTAL'] += 1
                except Exception as e:
                    continue
            
            if new_trades:
                trading_state['trades'] = new_trades
                trading_state['trades_executed'] += len(new_trades)
                trading_state['last_trade_time'] = datetime.now(timezone.utc).isoformat()
                trading_state['edge_history'].extend([t['edge'] for t in new_trades])
                if len(trading_state['edge_history']) > 100:
                    trading_state['edge_history'] = trading_state['edge_history'][-100:]
            
            trading_state['status'] = 'RUNNING'
            save_json('quant_state.json', trading_state)
            
            print(f"Cycle {trading_state['cycle']}: Found {len(new_trades)} trades, scanned {len(liquid)} markets")
            
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
    <title>POLYMARKET QUANT &lt;GO&gt;</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bloomberg-orange: #ff6600;
            --bloomberg-black: #000000;
            --bloomberg-dark: #0a0a0a;
            --bloomberg-gray: #1a1a1a;
            --bloomberg-panel: #111111;
            --bloomberg-border: #333333;
            --bloomberg-text: #ff9900;
            --bloomberg-text-dim: #996600;
            --positive: #00ff00;
            --negative: #ff0000;
            --neutral: #ffcc00;
        }
        
        body {
            background: #000;
            color: #ff9900;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 11px;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Top Bar */
        .topbar {
            background: linear-gradient(90deg, #000 0%, #1a1a00 50%, #000 100%);
            border-bottom: 2px solid #ff6600;
            padding: 8px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 2px;
        }
        
        .logo span { color: #ff6600; }
        
        .topbar-info {
            display: flex;
            gap: 30px;
            font-size: 11px;
        }
        
        .topbar-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .topbar-label { color: #666; }
        .topbar-value { color: #ff9900; font-weight: 600; }
        
        /* Main Grid */
        .main-container {
            display: grid;
            grid-template-columns: 280px 1fr 320px;
            grid-template-rows: auto 1fr auto;
            height: calc(100vh - 45px);
            gap: 1px;
            background: #333;
        }
        
        /* Panels */
        .panel {
            background: #0a0a0a;
            border: 1px solid #222;
            overflow: hidden;
        }
        
        .panel-header {
            background: linear-gradient(180deg, #1a1a1a, #111);
            border-bottom: 1px solid #333;
            padding: 6px 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .panel-title {
            font-size: 10px;
            font-weight: 600;
            color: #ff9900;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        
        .panel-badge {
            background: #1a1a00;
            color: #ff9900;
            padding: 2px 6px;
            font-size: 9px;
            border: 1px solid #333;
        }
        
        .panel-body {
            padding: 8px;
            overflow-y: auto;
            height: calc(100% - 28px);
        }
        
        /* Market Table */
        .market-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 10px;
        }
        
        .market-table th {
            text-align: left;
            padding: 4px 6px;
            color: #666;
            font-weight: 400;
            border-bottom: 1px solid #222;
            white-space: nowrap;
        }
        
        .market-table td {
            padding: 5px 6px;
            border-bottom: 1px solid #151515;
            white-space: nowrap;
        }
        
        .market-table tr:hover { background: #111; }
        .market-table tr.selected { background: #1a1a00; }
        
        .price-up { color: #00ff00; }
        .price-down { color: #ff0000; }
        
        .cat-sports { color: #4a9eff; }
        .cat-crypto { color: #ff9900; }
        .cat-politics { color: #ff4a4a; }
        .cat-business { color: #4aff4a; }
        .cat-tech { color: #ff4aff; }
        
        /* Trades Panel */
        .trade-card {
            background: #0d0d0d;
            border: 1px solid #222;
            margin-bottom: 6px;
            padding: 8px;
            border-left: 3px solid #ff6600;
        }
        
        .trade-card.sell { border-left-color: #ff0000; }
        
        .trade-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
        }
        
        .trade-action {
            font-weight: 700;
            font-size: 11px;
        }
        
        .trade-action.buy { color: #00ff00; }
        .trade-action.sell { color: #ff0000; }
        
        .trade-question {
            color: #888;
            font-size: 9px;
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .trade-meta {
            display: flex;
            justify-content: space-between;
            font-size: 9px;
            color: #555;
        }
        
        .trade-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4px;
            margin-top: 4px;
            padding-top: 4px;
            border-top: 1px solid #222;
        }
        
        .trade-stat {
            text-align: center;
        }
        
        .trade-stat-label { color: #444; font-size: 8px; }
        .trade-stat-value { color: #ff9900; font-weight: 600; }
        
        /* Analytics */
        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }
        
        .stat-box {
            background: #0d0d0d;
            border: 1px solid #222;
            padding: 10px;
            text-align: center;
        }
        
        .stat-box-value {
            font-size: 18px;
            font-weight: 700;
            color: #ff9900;
        }
        
        .stat-box-value.positive { color: #00ff00; }
        .stat-box-value.negative { color: #ff0000; }
        
        .stat-box-label {
            font-size: 9px;
            color: #555;
            margin-top: 3px;
        }
        
        /* AI Insights */
        .ai-insight {
            background: #0d0d0d;
            border: 1px solid #222;
            padding: 8px;
            margin-bottom: 6px;
            display: flex;
            align-items: flex-start;
            gap: 8px;
        }
        
        .ai-icon {
            width: 20px;
            height: 20px;
            background: #1a1a00;
            border: 1px solid #ff6600;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
        }
        
        .ai-content { flex: 1; }
        
        .ai-type {
            font-size: 9px;
            font-weight: 600;
            color: #ff6600;
            margin-bottom: 2px;
        }
        
        .ai-message {
            font-size: 10px;
            color: #888;
        }
        
        /* Sector Bar */
        .sector-item {
            margin-bottom: 8px;
        }
        
        .sector-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 3px;
            font-size: 10px;
        }
        
        .sector-name { color: #666; }
        .sector-vol { color: #ff9900; }
        
        .sector-bar {
            height: 8px;
            background: #111;
            border: 1px solid #222;
        }
        
        .sector-fill {
            height: 100%;
            background: linear-gradient(90deg, #ff6600, #ff9900);
        }
        
        /* Order Book */
        .ob-row {
            display: flex;
            justify-content: space-between;
            padding: 3px 5px;
            font-size: 10px;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .ob-bid { color: #00ff00; }
        .ob-ask { color: #ff0000; }
        
        .ob-bar-container {
            flex: 1;
            margin: 0 10px;
            height: 10px;
            background: #111;
            position: relative;
        }
        
        .ob-bar {
            position: absolute;
            height: 100%;
            top: 0;
        }
        
        .ob-bar.bid { background: #003300; right: 50%; }
        .ob-bar.ask { background: #330000; left: 50%; }
        
        /* News Ticker */
        .ticker {
            background: #0a0a0a;
            border-top: 1px solid #222;
            padding: 5px 15px;
            display: flex;
            align-items: center;
            gap: 15px;
            font-size: 10px;
            white-space: nowrap;
            overflow: hidden;
        }
        
        .ticker-label {
            background: #ff6600;
            color: #000;
            padding: 2px 8px;
            font-weight: 700;
            flex-shrink: 0;
        }
        
        .ticker-content {
            color: #666;
            animation: ticker 20s linear infinite;
        }
        
        @keyframes ticker {
            0% { transform: translateX(100%); }
            100% { transform: translateX(-100%); }
        }
        
        /* Status Bar */
        .status-bar {
            background: #000;
            border-top: 1px solid #333;
            padding: 4px 15px;
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: #555;
        }
        
        .status-item { display: flex; align-items: center; gap: 5px; }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; }
        .status-dot.green { background: #00ff00; }
        .status-dot.red { background: #ff0000; }
        .status-dot.orange { background: #ff6600; }
        
        /* Command Line */
        .cmdline {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #0a0a0a;
            border-top: 1px solid #333;
            padding: 8px 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .cmdline-prompt {
            color: #ff6600;
            font-weight: 700;
        }
        
        .cmdline-input {
            background: transparent;
            border: none;
            color: #ff9900;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            flex: 1;
            outline: none;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0a0a0a; }
        ::-webkit-scrollbar-thumb { background: #333; }
        ::-webkit-scrollbar-thumb:hover { background: #444; }
        
        /* Full width panels */
        .full-width {
            grid-column: 1 / -1;
        }
    </style>
</head>
<body>
    <div class="topbar">
        <div class="logo">POLYMARKET <span>QUANT</span> <GO></div>
        <div class="topbar-info">
            <div class="topbar-item">
                <span class="topbar-label">CYCLE</span>
                <span class="topbar-value" id="cycle">0</span>
            </div>
            <div class="topbar-item">
                <span class="topbar-label">STATUS</span>
                <span class="topbar-value" id="status">INIT</span>
            </div>
            <div class="topbar-item">
                <span class="topbar-label">PORTFOLIO</span>
                <span class="topbar-value" id="portfolio">$0</span>
            </div>
            <div class="topbar-item">
                <span class="topbar-label">TIME</span>
                <span class="topbar-value" id="clock">00:00:00</span>
            </div>
        </div>
    </div>
    
    <div class="main-container">
        <!-- Left Panel: Market Watch -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Market Watch</span>
                <span class="panel-badge" id="marketCount">0</span>
            </div>
            <div class="panel-body">
                <table class="market-table">
                    <thead>
                        <tr>
                            <th>MKT</th>
                            <th>PRICE</th>
                            <th>CHG</th>
                            <th>VOLUME</th>
                        </tr>
                    </thead>
                    <tbody id="marketTable"></tbody>
                </table>
            </div>
        </div>
        
        <!-- Center Panel: Trades & Positions -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Active Positions</span>
                <span class="panel-badge" id="tradeCount">0</span>
            </div>
            <div class="panel-body" id="tradesList"></div>
        </div>
        
        <!-- Right Panel: Analytics -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Analytics</span>
                <span class="panel-badge">REAL-TIME</span>
            </div>
            <div class="panel-body">
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-box-value" id="totalTrades">0</div>
                        <div class="stat-box-label">TOTAL TRADES</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-box-value positive" id="winRate">0%</div>
                        <div class="stat-box-label">WIN RATE</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-box-value" id="avgEdge">0%</div>
                        <div class="stat-box-label">AVG EDGE</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-box-value" id="maxEdge">0%</div>
                        <div class="stat-box-label">MAX EDGE</div>
                    </div>
                </div>
                
                <div style="margin-top:15px;">
                    <div class="panel-title" style="margin-bottom:8px;">AI Analysis</div>
                    <div id="aiInsights"></div>
                </div>
                
                <div style="margin-top:15px;">
                    <div class="panel-title" style="margin-bottom:8px;">Sector Breakdown</div>
                    <div id="sectorChart"></div>
                </div>
            </div>
        </div>
        
        <!-- Bottom Left: Order Book Sample -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Top Opportunities</span>
            </div>
            <div class="panel-body" id="opportunities"></div>
        </div>
        
        <!-- Bottom Center: Performance -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Performance Metrics</span>
            </div>
            <div class="panel-body">
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-box-value" id="marketsScanned">0</div>
                        <div class="stat-box-label">MKTS SCANNED</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-box-value" id="totalVol">$0</div>
                        <div class="stat-box-label">VOLUME SCANNED</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-box-value" id="avgTradeSize">$0</div>
                        <div class="stat-box-label">AVG SIZE</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-box-value" id="totalCost">$0</div>
                        <div class="stat-box-label">TOTAL COST</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Bottom Right: System -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">System</span>
            </div>
            <div class="panel-body">
                <div style="display:flex; flex-direction:column; gap:6px; font-size:10px;">
                    <div style="display:flex; justify-content:space-between;"><span style="color:#555;">MODE</span><span style="color:#ff9900;">PAPER</span></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#555;">API ERRORS</span><span style="color:#ff4444;" id="apiErrors">0</span></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#555;">UPTIME</span><span id="uptime">0h</span></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#555;">LAST TRADE</span><span id="lastTrade">-</span></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#555;">STRATEGY</span><span style="color:#00ff00;">QUANT</span></div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="ticker">
        <span class="ticker-label">NEWS</span>
        <div class="ticker-content" id="newsTicker">
            Quant Engine Running | Scanning Polymarket Markets | AI Analysis Active | Paper Trading Mode
        </div>
    </div>
    
    <div class="status-bar">
        <div class="status-item">
            <span class="status-dot green" id="statusDot"></span>
            <span id="statusText">CONNECTED</span>
        </div>
        <div class="status-item">
            <span>MARKETS: <span id="statusMarkets">0</span></span>
        </div>
        <div class="status-item">
            <span>API: <span id="statusApi">OK</span></span>
        </div>
        <div class="status-item">
            <span>RENDER.COM CLOUD</span>
        </div>
    </div>
    
    <div class="cmdline">
        <span class="cmdline-prompt">&gt;</span>
        <input type="text" class="cmdline-input" placeholder="Enter command..." id="cmdInput">
    </div>
    
    <script>
        function formatNum(n) { 
            if(n >= 1e9) return (n/1e9).toFixed(1) + 'B';
            if(n >= 1e6) return (n/1e6).toFixed(1) + 'M';
            if(n >= 1e3) return (n/1e3).toFixed(1) + 'K';
            return n.toFixed(0);
        }
        
        function formatTime(iso) {
            if(!iso) return '-';
            return new Date(iso).toLocaleTimeString();
        }
        
        function formatUptime(iso) {
            if(!iso) return '0h';
            const hrs = (new Date() - new Date(iso)) / 3600000;
            if(hrs < 1) return Math.round(hrs*60) + 'm';
            return Math.round(hrs) + 'h';
        }
        
        function catColor(cat) {
            const colors = {
                'Sports': 'cat-sports',
                'Crypto': 'cat-crypto', 
                'Politics': 'cat-politics',
                'Business': 'cat-business',
                'Tech': 'cat-tech',
                'Entertainment': 'cat-sports',
                'Science': 'cat-crypto'
            };
            return colors[cat] || '';
        }
        
        async function update() {
            try {
                const s = await fetch('/api/status').then(r=>r.json());
                const t = await fetch('/api/trades').then(r=>r.json());
                const m = await fetch('/api/markets').then(r=>r.json());
                
                // Header
                document.getElementById('clock').textContent = new Date().toLocaleTimeString();
                document.getElementById('cycle').textContent = s.cycle;
                document.getElementById('status').textContent = s.status;
                document.getElementById('portfolio').textContent = '$' + s.portfolio.toFixed(0);
                
                // Markets
                document.getElementById('marketCount').textContent = m.markets.length;
                const marketsHtml = m.markets.slice(0, 15).map(x => {
                    const chg = x.oneDayChange || 0;
                    const chgClass = chg >= 0 ? 'price-up' : 'price-down';
                    const chgSign = chg >= 0 ? '+' : '';
                    return '<tr><td class="' + catColor(x.category) + '">' + x.category.substring(0,4) + '</td><td>' + (x.price*100).toFixed(1) + '%</td><td class="' + chgClass + '">' + chgSign + (chg*100).toFixed(1) + '%</td><td>' + formatNum(x.volume) + '</td></tr>';
                }).join('');
                document.getElementById('marketTable').innerHTML = marketsHtml;
                
                // Trades
                document.getElementById('tradeCount').textContent = t.trades.length;
                const tradesHtml = t.trades.slice(0, 8).map(x => {
                    const isSell = x.action.includes('SELL');
                    return '<div class="trade-card ' + (isSell ? 'sell' : '') + '"><div class="trade-header"><span class="trade-action ' + (isSell ? 'sell' : 'buy') + '">' + x.action + '</span><span style="color:#666;font-size:9px;">' + x.category + '</span></div><div class="trade-question">' + x.question + '</div><div class="trade-meta"><span>$' + x.size.toFixed(2) + '</span><span>@ ' + (x.price*100).toFixed(1) + '%</span><span>Edge: ' + (x.edge*100).toFixed(1) + '%</span></div><div class="trade-stats"><div class="trade-stat"><div class="trade-stat-value">' + (x.prob_estimate*100).toFixed(1) + '%</div><div class="trade-stat-label">AI PROB</div></div><div class="trade-stat"><div class="trade-stat-value">' + (x.kelly*100).toFixed(1) + '%</div><div class="trade-stat-label">KELLY</div></div><div class="trade-stat"><div class="trade-stat-value">' + x.spread + '%</div><div class="trade-stat-label">SPREAD</div></div><div class="trade-stat"><div class="trade-stat-value">' + x.method + '</div><div class="trade-stat-label">METHOD</div></div></div></div>';
                }).join('');
                document.getElementById('tradesList').innerHTML = tradesHtml || '<div style="color:#444;text-align:center;padding:20px;">NO ACTIVE POSITIONS</div>';
                
                // Analytics
                document.getElementById('totalTrades').textContent = s.trades_executed;
                const winRate = (s.wins + s.losses) > 0 ? (s.wins / (s.wins + s.losses) * 100) : 0;
                document.getElementById('winRate').textContent = winRate.toFixed(0) + '%';
                
                const edges = t.trades.map(x => x.edge);
                const avgEdge = edges.length ? (edges.reduce((a,b)=>a+b,0) / edges.length * 100).toFixed(1) : 0;
                const maxEdge = edges.length ? (Math.max(...edges) * 100).toFixed(1) : 0;
                document.getElementById('avgEdge').textContent = avgEdge + '%';
                document.getElementById('maxEdge').textContent = maxEdge + '%';
                
                // AI Insights
                const insights = s.ai_insights || [];
                const aiHtml = insights.map(x => {
                    const icon = x.type === 'HOT' ? '🔥' : x.type === 'EDGE' ? '📈' : x.type === 'BIAS' ? '⚖️' : '🤖';
                    return '<div class="ai-insight"><div class="ai-icon">' + icon + '</div><div class="ai-content"><div class="ai-type">' + x.type + '</div><div class="ai-message">' + x.message + '</div></div></div>';
                }).join('');
                document.getElementById('aiInsights').innerHTML = aiHtml || '<div style="color:#444;font-size:10px;text-align:center;">ANALYZING MARKETS...</div>';
                
                // Sectors
                const sectors = m.market_insights || [];
                const totalVol = sectors.reduce((a,b)=>a+b.volume,0);
                const sectorHtml = sectors.slice(0,6).map(x => {
                    const pct = totalVol ? (x.volume / totalVol * 100) : 0;
                    return '<div class="sector-item"><div class="sector-header"><span class="sector-name">' + x.category + '</span><span class="sector-vol">$' + formatNum(x.volume) + '</span></div><div class="sector-bar"><div class="sector-fill" style="width:' + pct + '%"></div></div></div>';
                }).join('');
                document.getElementById('sectorChart').innerHTML = sectorHtml || '<div style="color:#444;font-size:10px;">NO DATA</div>';
                
                // Performance
                document.getElementById('marketsScanned').textContent = s.markets_scanned;
                document.getElementById('totalVol').textContent = '$' + formatNum(s.total_volume_scanned);
                
                const totalSize = t.trades.reduce((a,b)=>a+b.size,0);
                const avgSize = t.trades.length ? totalSize / t.trades.length : 0;
                const totalCost = t.trades.reduce((a,b)=>a+b.cost,0);
                
                document.getElementById('avgTradeSize').textContent = '$' + avgSize.toFixed(2);
                document.getElementById('totalCost').textContent = '$' + totalCost.toFixed(2);
                
                // System
                document.getElementById('apiErrors').textContent = s.api_errors;
                document.getElementById('uptime').textContent = formatUptime(s.startup_time);
                document.getElementById('lastTrade').textContent = s.last_trade_time ? formatTime(s.last_trade_time) : 'NONE';
                
                // Status
                document.getElementById('statusMarkets').textContent = m.markets.length;
                document.getElementById('statusDot').className = 'status-dot ' + (s.status === 'RUNNING' ? 'green' : 'red');
                document.getElementById('statusText').textContent = s.status === 'RUNNING' ? 'ACTIVE' : 'ERROR';
                
                // Top Opportunities
                const oppHtml = m.markets.slice(0,5).map(x => {
                    return '<div style="padding:6px;margin-bottom:4px;background:#0d0d0d;border-left:2px solid #ff6600;"><div style="display:flex;justify-content:space-between;"><span style="color:#888;font-size:9px;">' + x.category + '</span><span style="color:#00ff00;font-size:9px;">VOL: ' + formatNum(x.volume) + '</span></div><div style="font-size:10px;margin:3px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + x.question.substring(0,40) + '</div><div style="display:flex;justify-content:space-between;font-size:9px;"><span style="color:#666;">$' + (x.price*100).toFixed(1) + '</span><span style="color:' + ((x.oneDayChange||0) >= 0 ? '#00ff00':'#ff0000') + '">' + ((x.oneDayChange||0)*100).toFixed(1) + '%</span></div></div>';
                }).join('');
                document.getElementById('opportunities').innerHTML = oppHtml;
                
            } catch(e) {
                console.error(e);
            }
        }
        
        // Command line
        document.getElementById('cmdInput').addEventListener('keypress', function(e) {
            if(e.key === 'Enter') {
                const cmd = this.value.toUpperCase();
                if(cmd === 'REFRESH') {
                    update();
                } else if(cmd === 'STATUS') {
                    alert('System Status: Running');
                } else if(cmd === 'HELP') {
                    alert('Commands: REFRESH, STATUS, CLEAR');
                }
                this.value = '';
            }
        });
        
        update();
        setInterval(update, 5000);
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
        'portfolio_start': trading_state.get('portfolio_start', 1000),
        'trades_executed': trading_state['trades_executed'],
        'wins': trading_state['wins'],
        'losses': trading_state['losses'],
        'status': trading_state['status'],
        'last_error': trading_state.get('last_error', ''),
        'last_update': datetime.now(timezone.utc).isoformat(),
        'startup_time': trading_state.get('startup_time'),
        'markets_scanned': trading_state.get('markets_scanned', 0),
        'api_errors': trading_state.get('api_errors', 0),
        'last_trade_time': trading_state.get('last_trade_time'),
        'total_volume_scanned': trading_state.get('total_volume_scanned', 0),
        'strategy_stats': dict(trading_state.get('strategy_stats', {})),
        'edge_history': trading_state.get('edge_history', []),
        'ai_insights': trading_state.get('ai_insights', []),
        'sectors': dict(trading_state.get('sectors', {}))
    })

@app.route('/api/trades')
def api_trades():
    return jsonify({'trades': trading_state.get('trades', [])[:20]})

@app.route('/api/markets')
def api_markets():
    return jsonify({
        'markets': trading_state.get('top_markets', []),
        'market_insights': trading_state.get('market_insights', [])
    })

@app.route('/api/ai')
def api_ai():
    return jsonify({
        'insights': trading_state.get('ai_insights', []),
        'sectors': dict(trading_state.get('sectors', {}))
    })

@app.route('/api/logs')
def api_logs():
    return jsonify({'logs': [
        {'time': datetime.now(timezone.utc).isoformat(), 'type': 'STATUS', 'message': f"Cycle {trading_state['cycle']} - {trading_state['status']}"}
    ]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Polymarket Bloomberg Terminal on port {port}")
    app.run(host='0.0.0.0', port=port)
