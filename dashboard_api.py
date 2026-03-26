#!/usr/bin/env python3
"""
Dashboard API - Real-time data for the trading dashboard
"""
import os
import json
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template
from flask_cors import CORS

os.environ['POLY_BUILDER_KEY'] = '019d2b2f-b867-7daf-ac0b-92da916743fd'
os.environ['POLY_BUILDER_SECRET'] = 'g8_tldos1eNeC1Ri6Itnaz49ibSBRCQKhYQCgK30qos='
os.environ['POLY_BUILDER_PASSPHRASE'] = 'bd017fc2ea140a60e42763d2383935fa6dd33b0d972ba08f7bf96d0c5cc41059'

app = Flask(__name__)
CORS(app)

DATA_DIR = 'D:/polymarket_ai_bot'


def load_json(filename, default=None):
    """Load JSON from file"""
    try:
        with open(f'{DATA_DIR}/{filename}', 'r') as f:
            return json.load(f)
    except:
        return default if default is not None else {}


def save_json(filename, data):
    """Save JSON to file"""
    with open(f'{DATA_DIR}/{filename}', 'w') as f:
        json.dump(data, f, indent=2)


@app.route('/')
def index():
    """Dashboard home"""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """Overall system status"""
    state = load_json('trader_state.json', {})
    perf = load_json('performance.json', {'trades': [], 'wins': 0, 'losses': 0})
    markets = load_json('cycle_markets.json', [])
    
    # Calculate metrics
    pending = state.get('pending_trades', [])
    portfolio = state.get('portfolio', 1000)
    exposed = sum(t.get('cost', 0) for t in pending)
    cash = portfolio - exposed
    
    wins = perf.get('wins', 0)
    losses = perf.get('losses', 0)
    total_trades = len(perf.get('trades', []))
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    
    return jsonify({
        'status': 'RUNNING' if pending else 'SCANNING',
        'cycle': state.get('cycle', 0),
        'last_update': datetime.now(timezone.utc).isoformat(),
        'portfolio': portfolio,
        'exposed': round(exposed, 2),
        'cash': round(cash, 2),
        'pending_trades': len(pending),
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': round(win_rate, 1),
        'markets_scanned': len(markets)
    })


@app.route('/api/trades')
def api_trades():
    """Current pending trades"""
    state = load_json('trader_state.json', {})
    trades = state.get('pending_trades', [])
    
    # Add simulated P&L (would need real resolution data)
    for t in trades:
        t['pnl'] = 0  # Not resolved yet
        t['days_held'] = 0
    
    return jsonify({'trades': trades})


@app.route('/api/performance')
def api_performance():
    """Performance history"""
    perf = load_json('performance.json', {'trades': [], 'wins': 0, 'losses': 0})
    
    # Get recent trades
    recent_trades = perf.get('trades', [])[-20:]
    
    wins = perf.get('wins', 0)
    losses = perf.get('losses', 0)
    
    return jsonify({
        'total_trades': len(perf.get('trades', [])),
        'wins': wins,
        'losses': losses,
        'win_rate': round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
        'total_pnl': round(perf.get('total_pnl', 0), 2),
        'recent_trades': recent_trades
    })


@app.route('/api/markets')
def api_markets():
    """Scanned markets"""
    markets = load_json('cycle_markets.json', [])
    return jsonify({'markets': markets[:20]})


@app.route('/api/insights')
def api_insights():
    """AI insights and analysis"""
    perf = load_json('performance.json', {})
    trades = perf.get('trades', [])
    
    insights = []
    
    # Analyze recent performance
    if len(trades) > 0:
        # Edge accuracy
        correct = sum(1 for t in trades if t.get('result') != 'PENDING')
        if correct > 0:
            insights.append(f"Analysis accuracy: {correct} trades evaluated")
    
    # Market opportunities
    markets = load_json('cycle_markets.json', [])
    if markets:
        high_edge = [m for m in markets[:10] if abs(m.get('edge', 0)) > 0.15]
        if high_edge:
            insights.append(f"Found {len(high_edge)} high-edge opportunities")
    
    # System status
    insights.append("Autonomous agent running - scanning every 60 seconds")
    insights.append("Tools: Web search, crypto prices, self-improvement active")
    
    return jsonify({'insights': insights})


@app.route('/api/portfolio')
def api_portfolio():
    """Portfolio summary"""
    state = load_json('trader_state.json', {})
    portfolio = state.get('portfolio', 1000)
    trades = state.get('pending_trades', [])
    
    # Group by action
    buy_yes = [t for t in trades if 'BUY' in t.get('action', '')]
    sell_yes = [t for t in trades if 'SELL' in t.get('action', '')]
    
    exposed = sum(t.get('cost', 0) for t in trades)
    cash = portfolio - exposed
    
    return jsonify({
        'total': portfolio,
        'exposed': round(exposed, 2),
        'cash': round(cash, 2),
        'positions': len(trades),
        'buy_yes_count': len(buy_yes),
        'sell_yes_count': len(sell_yes),
        'avg_position_size': round(exposed / len(trades), 2) if trades else 0
    })


@app.route('/api/logs')
def api_logs():
    """Recent activity logs"""
    logs = []
    
    # Read from state
    state = load_json('trader_state.json', {})
    if state.get('pending_trades'):
        for t in state['pending_trades']:
            logs.append({
                'time': t.get('timestamp', ''),
                'type': 'TRADE',
                'message': f"{t.get('action')} ${t.get('size')} on {t.get('question', '')[:40]}"
            })
    
    # Add cycle info
    logs.append({
        'time': datetime.now(timezone.utc).isoformat(),
        'type': 'STATUS',
        'message': f"Cycle {state.get('cycle', 0)} completed - scanning markets"
    })
    
    return jsonify({'logs': logs[-20:]})


if __name__ == '__main__':
    print("=" * 60)
    print("POLYMARKET AUTONOMOUS TRADER DASHBOARD")
    print("=" * 60)
    print()
    print("Dashboard: http://localhost:5000")
    print("API:       http://localhost:5000/api/status")
    print()
    app.run(debug=True, port=5000, host='0.0.0.0')