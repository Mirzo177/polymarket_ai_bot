#!/usr/bin/env python3
"""
Polymarket Quant Trading Engine - Professional Edition
"""
import os
import json
import time
import uuid
import threading
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
    'price_alerts': []
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
    
    def get_market_details(self, condition_id):
        try:
            resp = httpx.get(f"{self.gamma_url}/markets", 
                            params={'conditionId': condition_id},
                            timeout=15)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return None

def categorize_market(question):
    q = question.lower()
    categories = {
        'Sports': ['nfl', 'nba', 'nhl', 'mlb', 'football', 'basketball', 'hockey', 'soccer', 'tennis', 'golf', 'boxing', 'ufc', 'mma', 'world cup', 'olympics', 'stanley cup', 'super bowl', 'championship', 'playoffs', 'game'],
        'Crypto': ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana', 'dogecoin', 'ordinal', 'ether', 'token', 'blockchain'],
        'Politics': ['president', 'election', 'trump', 'biden', 'congress', 'senate', 'governor', 'mayor', 'vote', 'republican', 'democrat', 'party', 'reelection'],
        'Business': ['stock', 'market', 'fed', 'economy', 'gdp', 'recession', 'earnings', 'ipo', 'merge', 'acquisition', 'company', 'apple', 'google', 'microsoft', 'amazon', 'tesla', 'meta'],
        'Entertainment': ['oscar', 'grammy', 'emmy', 'tony', 'movie', 'album', 'song', 'chart', 'box office', 'netflix', 'spotify', 'streaming'],
        'Tech': ['ai', 'artificial intelligence', 'openai', 'google', 'microsoft', 'apple', 'product', 'launch', 'release', 'announce'],
        'Science': ['space', 'nasa', 'moon', 'mars', 'climate', 'weather', 'earthquake', 'eruption'],
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
        return {'probability': fundamental, 'confidence': 0.6}

class KellyCriterion:
    def calculate(self, probability, odds):
        if odds <= 1:
            return {'kelly_fraction': 0, 'edge': 0}
        b = odds - 1
        expected_value = (probability * b) - (1 - probability)
        kelly = 0.05 if expected_value > 0 else 0
        return {'kelly_fraction': kelly, 'edge': expected_value}

class QuantEngine:
    def __init__(self):
        self.api = PolymarketAPI()
        self.prob = ProbabilityEstimator()
        self.kelly = KellyCriterion()
    
    def scan_and_trade(self):
        global trading_state
        try:
            trading_state['status'] = 'SCANNING'
            markets = self.api.get_markets(50)
            
            # Process and categorize markets
            market_data = []
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
                        
                        market_data.append({
                            'id': m.get('id'),
                            'question': m.get('question', ''),
                            'volume': vol,
                            'liquidity': liq,
                            'price': price,
                            'bid': bid,
                            'ask': ask,
                            'spread': spread,
                            'category': categorize_market(m.get('question', '')),
                            'volume24hr': float(m.get('volume24hr') or 0),
                            'volume1wk': float(m.get('volume1wk') or 0),
                            'oneDayChange': float(m.get('oneDayPriceChange') or 0),
                            'oneHourChange': float(m.get('oneHourPriceChange') or 0),
                            'oneWeekChange': float(m.get('oneWeekPriceChange') or 0),
                            'endDate': m.get('endDate'),
                            'active': m.get('active', True)
                        })
                except:
                    continue
            
            # Filter liquid markets
            liquid = [m for m in market_data if m['volume'] > 5000 and m['liquidity'] > 2000]
            liquid.sort(key=lambda x: x['volume'], reverse=True)
            
            # Update top markets
            trading_state['top_markets'] = liquid[:15]
            trading_state['markets_scanned'] = len(liquid)
            trading_state['total_volume_scanned'] = sum(m['volume'] for m in liquid)
            
            # Category breakdown
            category_vol = defaultdict(float)
            for m in liquid:
                category_vol[m['category']] += m['volume']
            trading_state['market_insights'] = [
                {'category': k, 'volume': v} for k, v in sorted(category_vol.items(), key=lambda x: -x[1])[:8]
            ]
            
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
                                'spread': round(m['spread'], 2)
                            }
                            new_trades.append(trade)
                            trading_state['strategy_stats']['FUNDAMENTAL'] += 1
                except Exception as e:
                    continue
            
            # Update trade history
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

@app.route('/dashboard')
def dashboard():
    return '''<!DOCTYPE html>
<html>
<head>
    <title>Polymarket Quant Terminal</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0e17; color: #e0e0e0; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 13px; min-height: 100vh; }
        .container { max-width: 1800px; margin: 0 auto; padding: 15px; }
        
        /* Header */
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 15px 20px; background: linear-gradient(90deg, #1a2332, #0d1520); border-radius: 8px; border: 1px solid #2a3a4d; }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo h1 { font-size: 18px; font-weight: 600; color: #00d4ff; letter-spacing: 1px; }
        .logo span { color: #00ff88; }
        .status-bar { display: flex; gap: 20px; align-items: center; }
        .status-badge { padding: 6px 14px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .status-badge.running { background: #00ff8820; color: #00ff88; border: 1px solid #00ff8840; }
        .status-badge.error { background: #ff475720; color: #ff4757; border: 1px solid #ff475740; }
        .clock { color: #888; font-size: 12px; }
        
        /* Stats Grid */
        .stats-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: #131a26; padding: 15px; border-radius: 6px; border: 1px solid #1e2a3a; }
        .stat-card:hover { border-color: #00d4ff40; }
        .stat-label { color: #5a6a7a; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .stat-value { font-size: 22px; font-weight: 700; color: #fff; }
        .stat-value.green { color: #00ff88; }
        .stat-value.red { color: #ff4757; }
        .stat-value.cyan { color: #00d4ff; }
        .stat-sub { font-size: 10px; color: #5a6a7a; margin-top: 4px; }
        
        /* Main Grid */
        .main-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 15px; }
        
        /* Panel */
        .panel { background: #131a26; border-radius: 8px; border: 1px solid #1e2a3a; overflow: hidden; }
        .panel-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: #1a2332; border-bottom: 1px solid #2a3a4d; }
        .panel-title { font-size: 12px; font-weight: 600; color: #00d4ff; text-transform: uppercase; letter-spacing: 1px; }
        .panel-badge { background: #00d4ff20; color: #00d4ff; padding: 3px 8px; border-radius: 3px; font-size: 10px; }
        .panel-body { padding: 12px; max-height: 400px; overflow-y: auto; }
        
        /* Markets Table */
        .markets-table { width: 100%; border-collapse: collapse; }
        .markets-table th { text-align: left; padding: 8px; color: #5a6a7a; font-size: 10px; text-transform: uppercase; border-bottom: 1px solid #2a3a4d; }
        .markets-table td { padding: 10px 8px; border-bottom: 1px solid #1e2a3a; font-size: 12px; }
        .markets-table tr:hover { background: #1a233240; }
        .price-up { color: #00ff88; }
        .price-down { color: #ff4757; }
        .category-badge { padding: 2px 6px; border-radius: 3px; font-size: 9px; background: #2a3a4d; color: #8a9aaa; }
        
        /* Trades */
        .trade-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; margin-bottom: 8px; background: #0d1520; border-radius: 4px; border-left: 3px solid #00d4ff; }
        .trade-item.sell { border-left-color: #ff4757; }
        .trade-action { font-weight: 700; font-size: 11px; }
        .trade-action.buy { color: #00ff88; }
        .trade-action.sell { color: #ff4757; }
        .trade-details { flex: 1; margin-left: 10px; }
        .trade-question { color: #aaa; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 300px; }
        .trade-meta { display: flex; gap: 15px; margin-top: 4px; font-size: 10px; color: #5a6a7a; }
        .trade-value { text-align: right; }
        .trade-size { font-size: 14px; font-weight: 700; color: #fff; }
        .trade-edge { font-size: 10px; }
        .trade-edge.positive { color: #00ff88; }
        .trade-edge.negative { color: #ff4757; }
        
        /* Category Chart */
        .category-list { display: flex; flex-direction: column; gap: 8px; }
        .category-item { display: flex; align-items: center; gap: 10px; }
        .category-name { width: 80px; font-size: 11px; color: #aaa; }
        .category-bar { flex: 1; height: 16px; background: #1e2a3a; border-radius: 3px; overflow: hidden; }
        .category-fill { height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); border-radius: 3px; transition: width 0.3s; }
        .category-value { width: 60px; text-align: right; font-size: 10px; color: #5a6a7a; }
        
        /* Metrics */
        .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .metric-box { background: #0d1520; padding: 12px; border-radius: 4px; text-align: center; }
        .metric-value { font-size: 18px; font-weight: 700; color: #00d4ff; }
        .metric-label { font-size: 9px; color: #5a6a7a; margin-top: 4px; text-transform: uppercase; }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0d1520; }
        ::-webkit-scrollbar-thumb { background: #2a3a4d; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #3a4a5d; }
        
        @media (max-width: 1200px) {
            .stats-grid { grid-template-columns: repeat(3, 1fr); }
            .main-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">
                <h1>POLYMARKET <span>QUANT</span></h1>
                <span style="color:#5a6a7a;font-size:11px;">| AI TRADING ENGINE</span>
            </div>
            <div class="status-bar">
                <div class="status-badge running" id="statusBadge">RUNNING</div>
                <div class="clock" id="clock"></div>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Cycle</div>
                <div class="stat-value cyan" id="cycle">0</div>
                <div class="stat-sub" id="marketsScanned">0 markets</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Portfolio</div>
                <div class="stat-value" id="portfolio">$0</div>
                <div class="stat-sub">Paper Trading</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Trades Executed</div>
                <div class="stat-value cyan" id="trades">0</div>
                <div class="stat-sub" id="lastTrade">No trades yet</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value green" id="winRate">-</div>
                <div class="stat-sub" id="winsLosses">0W / 0L</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Avg Edge</div>
                <div class="stat-value green" id="avgEdge">-</div>
                <div class="stat-sub" id="totalEdge">Total: 0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Uptime</div>
                <div class="stat-value" id="uptime">0h</div>
                <div class="stat-sub" id="apiErrors">0 API errors</div>
            </div>
        </div>
        
        <div class="main-grid">
            <div>
                <div class="panel">
                    <div class="panel-header">
                        <span class="panel-title">Live Markets</span>
                        <span class="panel-badge" id="marketsCount">0</span>
                    </div>
                    <div class="panel-body">
                        <table class="markets-table">
                            <thead>
                                <tr>
                                    <th>Market</th>
                                    <th>Category</th>
                                    <th>Price</th>
                                    <th>24h Change</th>
                                    <th>Volume</th>
                                    <th>Spread</th>
                                </tr>
                            </thead>
                            <tbody id="marketsTable"></tbody>
                        </table>
                    </div>
                </div>
                
                <div class="panel" style="margin-top: 15px;">
                    <div class="panel-header">
                        <span class="panel-title">Recent Trades</span>
                        <span class="panel-badge" id="tradesCount">0</span>
                    </div>
                    <div class="panel-body" id="tradesList"></div>
                </div>
            </div>
            
            <div>
                <div class="panel">
                    <div class="panel-header">
                        <span class="panel-title">Volume by Category</span>
                    </div>
                    <div class="panel-body" id="categoryChart"></div>
                </div>
                
                <div class="panel" style="margin-top: 15px;">
                    <div class="panel-header">
                        <span class="panel-title">Performance Metrics</span>
                    </div>
                    <div class="panel-body">
                        <div class="metrics-grid">
                            <div class="metric-box">
                                <div class="metric-value" id="avgTradeSize">$0</div>
                                <div class="metric-label">Avg Trade Size</div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-value" id="totalCost">$0</div>
                                <div class="metric-label">Total Cost</div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-value" id="avgSpread">0%</div>
                                <div class="metric-label">Avg Spread</div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-value" id="maxEdge">0%</div>
                                <div class="metric-label">Max Edge</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="panel" style="margin-top: 15px;">
                    <div class="panel-header">
                        <span class="panel-title">System Status</span>
                    </div>
                    <div class="panel-body">
                        <div style="display:flex; flex-direction:column; gap:8px; font-size:11px;">
                            <div style="display:flex; justify-content:space-between;"><span style="color:#5a6a7a;">Status</span><span id="sysStatus" style="color:#00ff88;">RUNNING</span></div>
                            <div style="display:flex; justify-content:space-between;"><span style="color:#5a6a7a;">Markets Scanned</span><span id="sysMarkets">0</span></div>
                            <div style="display:flex; justify-content:space-between;"><span style="color:#5a6a7a;">Total Volume</span><span id="sysVolume">$0</span></div>
                            <div style="display:flex; justify-content:space-between;"><span style="color:#5a6a7a;">API Errors</span><span id="sysErrors" style="color:#ff4757;">0</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function formatNum(n) { 
            if(n >= 1e6) return (n/1e6).toFixed(1) + 'M';
            if(n >= 1e3) return (n/1e3).toFixed(1) + 'K';
            return n.toFixed(0);
        }
        
        function formatTime(iso) {
            if(!iso) return '-';
            const d = new Date(iso);
            return d.toLocaleTimeString();
        }
        
        function formatUptime(iso) {
            if(!iso) return '0h';
            const start = new Date(iso);
            const now = new Date();
            const hrs = (now - start) / 3600000;
            if(hrs < 1) return Math.round(hrs*60) + 'm';
            return Math.round(hrs) + 'h';
        }
        
        async function update() {
            try {
                const s = await fetch('/api/status').then(r=>r.json());
                const t = await fetch('/api/trades').then(r=>r.json());
                const m = await fetch('/api/markets').then(r=>r.json());
                
                // Header
                document.getElementById('clock').textContent = new Date().toLocaleTimeString();
                document.getElementById('statusBadge').textContent = s.status;
                document.getElementById('statusBadge').className = 'status-badge ' + (s.status === 'RUNNING' ? 'running' : 'error');
                
                // Stats
                document.getElementById('cycle').textContent = s.cycle;
                document.getElementById('marketsScanned').textContent = s.markets_scanned + ' markets';
                document.getElementById('portfolio').textContent = '$' + s.portfolio.toFixed(0);
                document.getElementById('trades').textContent = s.trades_executed;
                document.getElementById('lastTrade').textContent = s.last_trade_time ? 'Last: ' + formatTime(s.last_trade_time) : 'No trades';
                
                const winRate = s.trades_executed > 0 ? (s.wins / (s.wins + s.losses) * 100) : 0;
                document.getElementById('winRate').textContent = s.trades_executed > 0 ? winRate.toFixed(0) + '%' : '-';
                document.getElementById('winsLosses').textContent = s.wins + 'W / ' + s.losses + 'L';
                
                const edges = t.trades.map(x => x.edge);
                const avgEdge = edges.length ? (edges.reduce((a,b)=>a+b,0) / edges.length * 100).toFixed(1) : 0;
                const maxEdge = edges.length ? (Math.max(...edges) * 100).toFixed(1) : 0;
                document.getElementById('avgEdge').textContent = avgEdge + '%';
                document.getElementById('totalEdge').textContent = 'Total: ' + (edges.reduce((a,b)=>a+b,0) * 100).toFixed(1) + '%';
                
                document.getElementById('uptime').textContent = formatUptime(s.startup_time);
                document.getElementById('apiErrors').textContent = s.api_errors + ' errors';
                
                // Markets
                document.getElementById('marketsCount').textContent = m.markets.length;
                const marketsHtml = m.markets.slice(0, 12).map(x => {
                    const change = x.oneDayChange || 0;
                    const changeClass = change >= 0 ? 'price-up' : 'price-down';
                    const changeSign = change >= 0 ? '+' : '';
                    return '<tr><td style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + x.question + '</td><td><span class="category-badge">' + x.category + '</span></td><td>' + (x.price*100).toFixed(1) + '%</td><td class="' + changeClass + '">' + changeSign + (change*100).toFixed(1) + '%</td><td>$' + formatNum(x.volume) + '</td><td>' + (x.spread||0).toFixed(1) + '%</td></tr>';
                }).join('');
                document.getElementById('marketsTable').innerHTML = marketsHtml;
                
                // Trades
                document.getElementById('tradesCount').textContent = t.trades.length;
                const tradesHtml = t.trades.map(x => {
                    const isSell = x.action.includes('SELL');
                    return '<div class="trade-item ' + (isSell ? 'sell' : '') + '"><div><div class="trade-action ' + (isSell ? 'sell' : 'buy') + '">' + x.action + '</div><div class="trade-details"><div class="trade-question">' + x.question + '</div><div class="trade-meta"><span>' + x.category + '</span><span>Kelly: ' + (x.kelly*100).toFixed(1) + '%</span><span>Spread: ' + (x.spread||0).toFixed(1) + '%</span></div></div></div><div class="trade-value"><div class="trade-size">$' + x.size.toFixed(2) + '</div><div class="trade-edge ' + (x.edge >= 0 ? 'positive' : 'negative') + '">Edge: ' + (x.edge*100).toFixed(1) + '%</div></div></div>';
                }).join('');
                document.getElementById('tradesList').innerHTML = tradesHtml || '<div style="color:#5a6a7a;text-align:center;padding:20px;">No trades this cycle</div>';
                
                // Categories
                const insights = m.market_insights || [];
                const totalVol = insights.reduce((a,b)=>a+b.volume,0);
                const catHtml = insights.map(x => {
                    const pct = totalVol ? (x.volume / totalVol * 100) : 0;
                    return '<div class="category-item"><div class="category-name">' + x.category + '</div><div class="category-bar"><div class="category-fill" style="width:' + pct + '%"></div></div><div class="category-value">$' + formatNum(x.volume) + '</div></div>';
                }).join('');
                document.getElementById('categoryChart').innerHTML = catHtml || '<div style="color:#5a6a7a;text-align:center;">No data</div>';
                
                // Metrics
                const totalSize = t.trades.reduce((a,b)=>a+b.size,0);
                const avgSize = t.trades.length ? totalSize / t.trades.length : 0;
                const totalCost = t.trades.reduce((a,b)=>a+b.cost,0);
                const avgSpread = t.trades.length ? t.trades.reduce((a,b)=>a+(b.spread||0),0) / t.trades.length : 0;
                
                document.getElementById('avgTradeSize').textContent = '$' + avgSize.toFixed(2);
                document.getElementById('totalCost').textContent = '$' + totalCost.toFixed(2);
                document.getElementById('avgSpread').textContent = avgSpread.toFixed(1) + '%';
                document.getElementById('maxEdge').textContent = maxEdge + '%';
                
                // System
                document.getElementById('sysStatus').textContent = s.status;
                document.getElementById('sysStatus').style.color = s.status === 'RUNNING' ? '#00ff88' : '#ff4757';
                document.getElementById('sysMarkets').textContent = s.markets_scanned;
                document.getElementById('sysVolume').textContent = '$' + formatNum(s.total_volume_scanned);
                document.getElementById('sysErrors').textContent = s.api_errors;
                
            } catch(e) {
                console.error(e);
            }
        }
        
        update();
        setInterval(update, 5000);
    </script>
</body>
</html>'''

@app.route('/')
def index():
    return '<h1>Polymarket Quant Trader</h1><p><a href="/dashboard">View Professional Dashboard</a></p>'

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
        'last_update': datetime.now(timezone.utc).isoformat(),
        'startup_time': trading_state.get('startup_time'),
        'markets_scanned': trading_state.get('markets_scanned', 0),
        'api_errors': trading_state.get('api_errors', 0),
        'last_trade_time': trading_state.get('last_trade_time'),
        'total_volume_scanned': trading_state.get('total_volume_scanned', 0),
        'strategy_stats': dict(trading_state.get('strategy_stats', {})),
        'edge_history': trading_state.get('edge_history', [])
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

@app.route('/api/insights')
def api_insights():
    return jsonify({
        'insights': trading_state.get('market_insights', []),
        'strategy_stats': dict(trading_state.get('strategy_stats', {})),
        'edge_history': trading_state.get('edge_history', [])
    })

@app.route('/api/logs')
def api_logs():
    return jsonify({'logs': [
        {'time': datetime.now(timezone.utc).isoformat(), 'type': 'STATUS', 'message': f"Cycle {trading_state['cycle']} - {trading_state['status']}"}
    ]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Polymarket Quant Engine on port {port}")
    app.run(host='0.0.0.0', port=port)
