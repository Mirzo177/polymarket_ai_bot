#!/usr/bin/env python3
"""
Quant Trading Engine - Web Version for Render (No polymarket-apis)
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

DATA_DIR = os.environ.get('DATA_DIR', '/tmp')

trading_state = {
    'cycle': 0,
    'trades': [],
    'portfolio': 1000,
    'trades_executed': 0,
    'wins': 0,
    'losses': 0,
    'status': 'STARTING'}

def save_json(filename, data):
    try:
        with open(f'{DATA_DIR}/{filename}', 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass

class PolymarketAPI:
    def __init__(self):
        self.gamma_url = "https://gamma-api.polymarket.com"
        
    def get_markets(self, limit=50):
        try:
            resp = httpx.get(f"{self.gamma_url}/markets", params={'limit': limit, 'closed': 'false'}, timeout=30)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Error: {e}")
        return []

class ProbabilityEstimator:
    def estimate(self, market_data):
        price = market_data.get('price_yes', 0.5)
        q = market_data.get('question', '').lower()
        if 'jesus christ' in q:
            fundamental = 0.02
        elif 'nhl' in q or 'stanley cup' in q:
            fundamental = min(0.15, price * 3) if price < 0.05 else price
        else:
            fundamental = price
        prob = 0.3 * fundamental + 0.7 * price
        return {'probability': prob, 'confidence': 0.5}

class KellyCriterion:
    def calculate(self, probability, odds):
        if odds <= 1: return {'kelly_fraction': 0, 'edge': 0}
        b = odds - 1
        expected_value = (probability * b) - (1 - probability)
        kelly = max(0, (b * probability - (1 - probability)) / b) if b > 0 else 0
        return {'kelly_fraction': min(kelly * 0.25, 0.25), 'edge': expected_value}

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
            if isinstance(markets, dict):
                markets = markets.get('markets', [])
            
            liquid = [m for m in markets if (m.get('volume24hr', 0) or 0) > 10000 and m.get('liquidity', 0) and m.get('outcomePrices')]
            liquid.sort(key=lambda x: x.get('volume24hr', 0), reverse=True)
            
            trading_state['cycle'] += 1
            new_trades = []
            
            for m in liquid[:10]:
                try:
                    prices = m.get('outcomePrices', [])
                    price = float(prices[0]) if prices else 0.5
                    prob_result = self.prob.estimate({'question': m.get('question', ''), 'price_yes': price})
                    edge = prob_result['probability'] - price
                    
                    if abs(edge) > 0.05:
                        odds = 1 / price if price > 0 else 1
                        kelly_result = self.kelly.calculate(prob_result['probability'], odds)
                        size = min(1000 * kelly_result['kelly_fraction'], 50)
                        
                        if size > 5:
                            trade = {
                                'id': str(uuid.uuid4())[:12],
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                                'action': 'BUY YES' if edge > 0 else 'SELL YES',
                                'size': round(size, 2),
                                'price': round(price, 4),
                                'cost': round(size * price, 2),
                                'question': m.get('question', ''),
                                'edge': round(edge, 4),
                                'strategy': 'FUNDAMENTAL',
                                'result': 'PENDING'
                            }
                            new_trades.append(trade)
                except:
                    continue
            
            trading_state['trades'] = new_trades
            trading_state['trades_executed'] += len(new_trades)
            trading_state['status'] = 'RUNNING'
            save_json('quant_state.json', trading_state)
        except Exception as e:
            trading_state['status'] = f'ERROR: {str(e)[:30]}'

def run_trading():
    engine = QuantEngine()
    while True:
        engine.scan_and_trade()
        time.sleep(60)

threading.Thread(target=run_trading, daemon=True).start()

@app.route('/')
def index():
    return jsonify({'name': 'Polymarket Quant Trader', 'status': trading_state['status'], 'cycle': trading_state['cycle']})

@app.route('/api/status')
def api_status():
    return jsonify({
        'mode': 'QUANT ENGINE', 'cycle': trading_state['cycle'], 'portfolio': trading_state['portfolio'],
        'trades_executed': trading_state['trades_executed'], 'wins': trading_state['wins'], 'losses': trading_state['losses'],
        'status': trading_state['status'], 'last_update': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/trades')
def api_trades():
    return jsonify({'trades': trading_state['trades'][:15]})

@app.route('/api/markets')
def api_markets():
    return jsonify({'markets': []})

@app.route('/api/insights')
def api_insights():
    return jsonify({'insights': [f"Quant running - Cycle {trading_state['cycle']}", f"{len(trading_state['trades'])} positions"]})

@app.route('/api/logs')
def api_logs():
    return jsonify({'logs': [{'time': datetime.now(timezone.utc).isoformat(), 'type': 'STATUS', 'message': f"Cycle {trading_state['cycle']}"}]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting on port {port}")
    app.run(host='0.0.0.0', port=port)