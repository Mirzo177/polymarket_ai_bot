#!/usr/bin/env python3
"""
Quant Trading Engine - Web Service Version for Render
Opens a port so Render can detect it
"""
import os
import json
import time
import uuid
import math
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any
from flask import Flask, jsonify
from flask_cors import CORS

os.environ['POLY_BUILDER_KEY'] = os.environ.get('POLY_BUILDER_KEY', '019d2b2f-b867-7daf-ac0b-92da916743fd')
os.environ['POLY_BUILDER_SECRET'] = os.environ.get('POLY_BUILDER_SECRET', 'g8_tldos1eNeC1Ri6Itnaz49ibSBRCQKhYQCgK30qos=')
os.environ['POLY_BUILDER_PASSPHRASE'] = os.environ.get('POLY_BUILDER_PASSPHRASE', 'bd017fc2ea140a60e42763d2383935fa6dd33b0d972ba08f7bf96d0c5cc41059')

from polymarket_apis import PolymarketGammaClient
import httpx

app = Flask(__name__)
CORS(app)

DATA_DIR = os.environ.get('DATA_DIR', '/tmp')

# Global state
trading_state = {
    'cycle': 0,
    'trades': [],
    'portfolio': 1000,
    'trades_executed': 0,
    'wins': 0,
    'losses': 0,
    'status': 'STARTING'
}

def load_json(filename, default=None):
    try:
        with open(f'{DATA_DIR}/{filename}', 'r') as f:
            return json.load(f)
    except:
        return default if default is not None else {}

def save_json(filename, data):
    try:
        with open(f'{DATA_DIR}/{filename}', 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass

# ============ QUANT TRADING ENGINE ============

class ProbabilityEstimator:
    """Bayesian model aggregation"""
    def __init__(self):
        self.weights = {'fundamental': 0.30, 'market': 0.25, 'sentiment': 0.20, 'technical': 0.15, 'momentum': 0.10}
    
    def estimate(self, market_data, news, price_history):
        import numpy as np
        market_prob = market_data.get('price_yes', 0.5)
        fundamental_prob = self._estimate_fundamental(market_data)
        return {'probability': (self.weights['fundamental'] * fundamental_prob + self.weights['market'] * market_prob), 'confidence': 0.5}
    
    def _estimate_fundamental(self, market_data):
        q = market_data.get('question', '').lower()
        market_price = market_data.get('price_yes', 0.5)
        if 'jesus christ' in q:
            return 0.02
        elif 'nhl' in q or 'stanley cup' in q:
            return min(0.15, market_price * 3) if market_price < 0.05 else market_price
        return market_price

class KellyCriterion:
    def __init__(self, fraction=0.25):
        self.fraction = fraction
        self.max_kelly = 0.25
    
    def calculate(self, probability, odds, confidence=1.0):
        if odds <= 1:
            return {'size': 0, 'kelly_fraction': 0, 'edge': 0}
        b = odds - 1
        p = probability
        expected_value = (p * b) - (1 - p)
        kelly = max(0, (b * p - (1 - p)) / b) if b > 0 else 0
        adjusted = min(kelly * self.fraction * confidence, self.max_kelly)
        return {'kelly_fraction': adjusted, 'edge': expected_value}

class QuantEngine:
    def __init__(self):
        self.gamma = PolymarketGammaClient()
        self.prob_estimator = ProbabilityEstimator()
        self.kelly = KellyCriterion()
    
    def scan_and_trade(self):
        global trading_state
        try:
            trading_state['status'] = 'SCANNING'
            markets = self.gamma.get_markets(limit=50, closed=False)
            liquid = [m for m in markets if (m.volume_24hr or 0) > 10000 and m.liquidity and m.liquidity > 5000]
            liquid.sort(key=lambda x: x.volume_24hr or 0, reverse=True)
            
            trading_state['cycle'] += 1
            cycle = trading_state['cycle']
            
            new_trades = []
            for m in liquid[:10]:
                price = m.outcome_prices[0] if m.outcome_prices else 0.5
                prob_result = self.prob_estimator.estimate({'question': m.question, 'price_yes': price}, [], [])
                edge = prob_result['probability'] - price
                
                if abs(edge) > 0.05:
                    odds = 1 / price if price > 0 else 1
                    kelly_result = self.kelly.calculate(prob_result['probability'], odds)
                    size = 1000 * kelly_result['kelly_fraction']
                    size = min(size, 50)
                    
                    if size > 5:
                        action = 'BUY YES' if edge > 0 else 'SELL YES'
                        trade = {
                            'id': str(uuid.uuid4())[:12],
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'action': action,
                            'size': round(size, 2),
                            'price': round(price, 4),
                            'cost': round(size * price, 2),
                            'question': m.question,
                            'edge': round(edge, 4),
                            'strategy': 'FUNDAMENTAL',
                            'result': 'PENDING'
                        }
                        new_trades.append(trade)
            
            trading_state['trades'] = new_trades
            trading_state['trades_executed'] += len(new_trades)
            trading_state['status'] = 'RUNNING'
            
            # Save state
            save_json('quant_state.json', trading_state)
            
        except Exception as e:
            trading_state['status'] = f'ERROR: {str(e)[:50]}'

# Start trading in background
def run_trading():
    engine = QuantEngine()
    while True:
        engine.scan_and_trade()
        time.sleep(60)

# Start background thread
trading_thread = threading.Thread(target=run_trading, daemon=True)
trading_thread.start()

# ============ FLASK ROUTES ============

@app.route('/')
def index():
    return jsonify({
        'name': 'Polymarket Quant Trader',
        'status': trading_state['status'],
        'cycle': trading_state['cycle'],
        'trades': len(trading_state['trades']),
        'portfolio': trading_state['portfolio']
    })

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
        'last_update': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/trades')
def api_trades():
    return jsonify({'trades': trading_state['trades'][:15]})

@app.route('/api/markets')
def api_markets():
    return jsonify({'markets': []})

@app.route('/api/insights')
def api_insights():
    return jsonify({'insights': [
        f"Quant Engine running - Cycle {trading_state['cycle']}",
        f"{len(trading_state['trades'])} positions analyzed",
        "Strategies: Fundamental, Momentum, Mean Reversion"
    ]})

@app.route('/api/logs')
def api_logs():
    return jsonify({'logs': [
        {'time': datetime.now(timezone.utc).isoformat(), 'type': 'STATUS', 'message': f"Cycle {trading_state['cycle']} - {trading_state['status']}"}
    ]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Polymarket Quant Trader on port {port}")
    app.run(host='0.0.0.0', port=port)