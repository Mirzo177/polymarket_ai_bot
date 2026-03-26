#!/usr/bin/env python3
"""Simple Dashboard Server"""
import os
import json
from datetime import datetime, timezone
from flask import Flask, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_DIR = 'D:/polymarket_ai_bot'

def load_json(filename, default=None):
    try:
        with open(f'{DATA_DIR}/{filename}', 'r') as f:
            return json.load(f)
    except:
        return default if default is not None else {}

@app.route('/')
def index():
    with open(f'{DATA_DIR}/templates/dashboard.html', 'r') as f:
        return f.read()

@app.route('/api/status')
def api_status():
    state = load_json('trader_state.json', {})
    perf = load_json('performance.json', {'trades': [], 'wins': 0, 'losses': 0})
    pending = state.get('pending_trades', [])
    portfolio = state.get('portfolio', 1000)
    exposed = sum(t.get('cost', 0) for t in pending)
    wins = perf.get('wins', 0)
    losses = perf.get('losses', 0)
    return jsonify({
        'status': 'RUNNING',
        'cycle': state.get('cycle', 0),
        'last_update': datetime.now(timezone.utc).isoformat(),
        'portfolio': portfolio,
        'exposed': round(exposed, 2),
        'cash': round(portfolio - exposed, 2),
        'pending_trades': len(pending),
        'total_trades': len(perf.get('trades', [])),
        'wins': wins,
        'losses': losses,
        'win_rate': round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0
    })

@app.route('/api/trades')
def api_trades():
    state = load_json('trader_state.json', {})
    return jsonify({'trades': state.get('pending_trades', [])})

@app.route('/api/performance')
def api_performance():
    perf = load_json('performance.json', {'trades': []})
    return jsonify({'trades': perf.get('trades', [])})

@app.route('/api/markets')
def api_markets():
    markets = load_json('cycle_markets.json', [])
    return jsonify({'markets': markets[:15]})

@app.route('/api/insights')
def api_insights():
    state = load_json('trader_state.json', {})
    markets = load_json('cycle_markets.json', [])
    insights = [
        f"Cycle {state.get('cycle', 0)} completed - scanning markets",
        "Tools active: Web search, crypto prices, self-improvement",
        f"{len(markets)} markets scanned for opportunities"
    ]
    high_edge = [m for m in markets if abs(m.get('edge', 0)) > 0.15]
    if high_edge:
        insights.append(f"Found {len(high_edge)} high-edge opportunities")
    return jsonify({'insights': insights})

@app.route('/api/logs')
def api_logs():
    state = load_json('trader_state.json', {})
    logs = []
    for t in state.get('pending_trades', [])[:10]:
        logs.append({'time': t.get('timestamp', ''), 'type': 'TRADE', 'message': f"{t.get('action')} ${t.get('size')} on {t.get('question', '')[:30]}..."})
    logs.append({'time': datetime.now(timezone.utc).isoformat(), 'type': 'STATUS', 'message': f"Cycle {state.get('cycle', 0)} completed"})
    return jsonify({'logs': logs})

if __name__ == '__main__':
    print("=" * 60)
    print("POLYMARKET DASHBOARD - http://localhost:5000")
    print("=" * 60)
    app.run(debug=False, port=5000, host='0.0.0.0')