#!/usr/bin/env python3
"""
Quant Trading Engine - Web Version for Render (Fixed)
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
    'last_error': ''}

def save_json(filename, data):
    try:
        with open(f'/tmp/{filename}', 'w') as f:
            json.dump(data, f, indent=2)
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
                # Handle both list and dict response
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('markets', [])
                return []
        except Exception as e:
            print(f"API Error: {e}")
            trading_state['last_error'] = str(e)[:50]
        return []

class ProbabilityEstimator:
    def estimate(self, market_data):
        import random
        price = market_data.get('price_yes', 0.5)
        q = market_data.get('question', '').lower()
        
        # Add some artificial edge for testing
        if price < 0.5:
            # If price is low, assume it's more likely than market says
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
        # Simplified: use fixed 5% of portfolio per trade with edge
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
            
            # Filter for liquid markets
            liquid = []
            for m in markets:
                try:
                    vol = float(m.get('volume') or m.get('volume24hr') or m.get('volume24Hr') or 0)
                    liq = float(m.get('liquidity') or 0)
                    prices_str = m.get('outcomePrices')
                    
                    # Parse JSON string if needed
                    if prices_str and isinstance(prices_str, str):
                        import json
                        prices = json.loads(prices_str)
                    else:
                        prices = prices_str or []
                    
                    if vol > 5000 and liq > 2000 and prices:
                        liquid.append(m)
                except:
                    continue
            
            # Sort by volume
            liquid.sort(key=lambda x: float(x.get('volume') or 0), reverse=True)
            
            trading_state['cycle'] += 1
            new_trades = []
            
            debug_info = []
            for m in liquid[:15]:
                try:
                    prices_str = m.get('outcomePrices')
                    if prices_str and isinstance(prices_str, str):
                        import json
                        prices = json.loads(prices_str)
                    else:
                        prices = prices_str or []
                    price = float(prices[0]) if prices else 0.5
                    
                    if price < 0.01 or price > 0.99:
                        continue
                    
                    prob_result = self.prob.estimate({
                        'question': m.get('question', ''), 
                        'price_yes': price
                    })
                    edge = prob_result['probability'] - price
                    debug_info.append(f"{m.get('question', '')[:30]}: p={price:.2f} edge={edge:.2f}")
                    
                    if abs(edge) > 0.01:  # Very low threshold to find more trades
                        odds = 1 / price if price > 0 else 1
                        kelly_result = self.kelly.calculate(prob_result['probability'], odds)
                        size = min(1000 * kelly_result['kelly_fraction'], 100)  # Max $100
                        
                        if size > 2:  # Lower minimum
                            action = 'BUY YES' if edge > 0 else 'SELL YES'
                            trade = {
                                'id': str(uuid.uuid4())[:12],
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                                'action': action,
                                'size': round(size, 2),
                                'price': round(price, 4),
                                'cost': round(size * price, 2),
                                'question': m.get('question', '')[:60],
                                'edge': round(edge, 4),
                                'volume': float(m.get('volume') or 0),
                                'strategy': 'FUNDAMENTAL',
                                'result': 'PENDING'
                            }
                            new_trades.append(trade)
                except Exception as e:
                    continue
            
            trading_state['trades'] = new_trades
            trading_state['trades_executed'] += len(new_trades)
            trading_state['status'] = 'RUNNING'
            save_json('quant_state.json', trading_state)
            
            print(f"Cycle {trading_state['cycle']}: Found {len(new_trades)} trades")
            
        except Exception as e:
            trading_state['status'] = f'ERROR: {str(e)[:30]}'
            print(f"Error: {e}")

def run_trading():
    engine = QuantEngine()
    while True:
        engine.scan_and_trade()
        time.sleep(60)

# Start trading in background
threading.Thread(target=run_trading, daemon=True).start()

DASHBOARD_HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>Polymarket Quant Bot</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: linear-gradient(135deg, #0f0c29, #1a1a3e); color: #fff; font-family: system-ui, sans-serif; min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; padding: 20px; background: rgba(0,0,0,0.4); border-radius: 15px; }
        .header h1 { background: linear-gradient(90deg, #00d4ff, #00ff88); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 25px; }
        .stat-card { background: rgba(0,0,0,0.4); padding: 20px; border-radius: 12px; border: 1px solid rgba(0,212,255,0.2); }
        .stat-label { color: #888; font-size: 12px; text-transform: uppercase; }
        .stat-value { font-size: 28px; font-weight: bold; color: #00d4ff; margin-top: 5px; }
        .trades-section { background: rgba(0,0,0,0.4); padding: 20px; border-radius: 15px; }
        .trades-section h2 { margin-bottom: 15px; color: #00ff88; }
        .trade { background: rgba(255,255,255,0.05); padding: 15px; margin-bottom: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; }
        .trade-action { font-weight: bold; color: #00ff88; }
        .trade-action.sell { color: #ff4757; }
        .refresh { position: fixed; bottom: 20px; right: 20px; background: #00d4ff; color: #000; padding: 12px 24px; border-radius: 25px; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Polymarket Quant Bot</h1>
            <span class="mode-badge" id="mode">Loading...</span>
        </div>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-label">Cycle</div><div class="stat-value" id="cycle">-</div></div>
            <div class="stat-card"><div class="stat-label">Portfolio</div><div class="stat-value" id="portfolio">$0</div></div>
            <div class="stat-card"><div class="stat-label">Trades</div><div class="stat-value" id="trades">0</div></div>
            <div class="stat-card"><div class="stat-label">Wins</div><div class="stat-value" id="wins">0</div></div>
            <div class="stat-card"><div class="stat-label">Losses</div><div class="stat-value" id="losses">0</div></div>
            <div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" id="status" style="font-size:18px">-</div></div>
        </div>
        <div class="trades-section">
            <h2>Recent Trades</h2>
            <div id="trades-list">Loading...</div>
        </div>
    </div>
    <a href="#" class="refresh" onclick="location.reload()">🔄 Refresh</a>
    <script>
        async function update() {
            try {
                const s = await fetch('/api/status').then(r=>r.json());
                document.getElementById('cycle').textContent = s.cycle;
                document.getElementById('portfolio').textContent = '$' + s.portfolio;
                document.getElementById('trades').textContent = s.trades_executed;
                document.getElementById('wins').textContent = s.wins;
                document.getElementById('losses').textContent = s.losses;
                document.getElementById('status').textContent = s.status;
                document.getElementById('mode').textContent = s.mode;
                
                const t = await fetch('/api/trades').then(r=>r.json());
                const list = document.getElementById('trades-list');
                if (t.trades.length === 0) {
                    list.innerHTML = '<p style="color:#888">No trades yet</p>';
                } else {
                    list.innerHTML = t.trades.map(x => '<div class="trade"><div><span class="trade-action '+(x.action.includes('SELL')?'sell':'')+'">'+x.action+'</span> '+x.question.substring(0,40)+'...</div><div>$'+x.size.toFixed(2)+' @ '+x.price.toFixed(2)+'</div></div>').join('');
                }
            } catch(e) { console.error(e); }
        }
        update(); setInterval(update, 10000);
    </script>
</body>
</html>'''

@app.route('/dashboard')
def dashboard():
    return DASHBOARD_HTML

@app.route('/')
def index():
    return '<h1>Polymarket Quant Trader</h1><p><a href="/dashboard">View Dashboard</a></p>'

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
        'last_update': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/trades')
def api_trades():
    return jsonify({'trades': trading_state['trades'][:20]})

@app.route('/api/markets')
def api_markets():
    return jsonify({'markets': []})

@app.route('/api/insights')
def api_insights():
    return jsonify({'insights': [
        f"Quant running - Cycle {trading_state['cycle']}",
        f"{len(trading_state['trades'])} positions",
        trading_state.get('last_error', '')
    ]})

@app.route('/api/logs')
def api_logs():
    return jsonify({'logs': [
        {'time': datetime.now(timezone.utc).isoformat(), 'type': 'STATUS', 'message': f"Cycle {trading_state['cycle']}"}
    ]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting on port {port}")
    app.run(host='0.0.0.0', port=port)