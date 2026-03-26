#!/usr/bin/env python3
"""
Enhanced Data API for Dashboard
"""
import os
import json
from datetime import datetime, timezone
from flask import Flask, jsonify
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

@app.route('/api/status')
def api_status():
    # Quant state
    quant = load_json('quant_state.json', {})
    # Trader state
    trader = load_json('trader_state.json', {})
    # Performance
    perf = load_json('performance.json', {'trades': [], 'wins': 0, 'losses': 0})
    
    portfolio = quant.get('portfolio', 1000)
    trades = quant.get('trades', [])
    
    # Calculate exposed (unique)
    unique_questions = set()
    exposed = 0
    for t in trades:
        q = t.get('question', '')
        if q not in unique_questions:
            unique_questions.add(q)
            exposed += t.get('cost', 0)
    
    cash = portfolio - exposed
    wins = quant.get('wins', 0)
    losses = quant.get('losses', 0)
    
    return jsonify({
        'mode': 'QUANT ENGINE',
        'cycle': quant.get('cycle', 0),
        'portfolio': portfolio,
        'exposed': round(exposed, 2),
        'cash': round(cash, 2),
        'positions': len(unique_questions),
        'trades_executed': quant.get('trades_executed', 0),
        'wins': wins,
        'losses': losses,
        'win_rate': round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
        'last_update': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/trades')
def api_trades():
    quant = load_json('quant_state.json', {})
    trades = quant.get('trades', [])
    
    # Deduplicate and format
    unique = []
    seen = set()
    for t in trades:
        q = t.get('question', '')
        if q not in seen:
            seen.add(q)
            # Handle action dict
            action = t.get('action', {})
            if isinstance(action, dict):
                action = action.get('action', 'UNKNOWN')
            unique.append({
                'id': t.get('id', ''),
                'timestamp': t.get('timestamp', ''),
                'action': action,
                'size': t.get('size', 0),
                'price': t.get('price', 0),
                'cost': t.get('cost', 0),
                'question': q,
                'edge': t.get('edge', 0),
                'confidence': t.get('confidence', 0),
                'strategy': t.get('strategy', ''),
                'estimated_prob': t.get('estimated_prob', 0),
                'result': t.get('result', 'PENDING')
            })
    
    return jsonify({'trades': unique[:20]})

@app.route('/api/markets')
def api_markets():
    markets = load_json('cycle_markets.json', [])
    return jsonify({'markets': markets[:20]})

@app.route('/api/performance')
def api_performance():
    quant = load_json('quant_state.json', {})
    perf = load_json('performance.json', {'trades': []})
    
    trades = quant.get('trades', [])
    
    # Strategy distribution
    strategies = {}
    for t in trades:
        s = t.get('strategy', 'UNKNOWN')
        strategies[s] = strategies.get(s, 0) + 1
    
    # Edge distribution
    edge_ranges = {'0-5%': 0, '5-10%': 0, '10-20%': 0, '20%+': 0}
    for t in trades:
        e = abs(t.get('edge', 0) * 100)
        if e < 5:
            edge_ranges['0-5%'] += 1
        elif e < 10:
            edge_ranges['5-10%'] += 1
        elif e < 20:
            edge_ranges['10-20%'] += 1
        else:
            edge_ranges['20%+'] += 1
    
    return jsonify({
        'total_trades': len(trades),
        'strategies': strategies,
        'edge_distribution': edge_ranges,
        'trades_executed': quant.get('trades_executed', 0),
        'wins': quant.get('wins', 0),
        'losses': quant.get('losses', 0)
    })

@app.route('/api/insights')
def api_insights():
    quant = load_json('quant_state.json', {})
    strategies = load_json('strategies.json', {})
    
    trades = quant.get('trades', [])
    cycle = quant.get('cycle', 0)
    
    insights = [
        f"Quant Engine running - Cycle {cycle}",
        f"{len(trades)} unique positions analyzed",
        "Strategies: Arbitrage, Momentum, Mean Reversion, Fundamental",
    ]
    
    # Count strategies used
    strat_counts = {}
    for t in trades:
        s = t.get('strategy', 'UNKNOWN')
        strat_counts[s] = strat_counts.get(s, 0) + 1
    
    if strat_counts:
        top_strat = max(strat_counts.items(), key=lambda x: x[1])
        insights.append(f"Most used: {top_strat[0]} ({top_strat[1]} times)")
    
    # High edge trades
    high_edge = [t for t in trades if t.get('edge', 0) > 0.15]
    if high_edge:
        insights.append(f"{len(high_edge)} high-edge opportunities (>15%)")
    
    return jsonify({'insights': insights})

@app.route('/api/logs')
def api_logs():
    quant = load_json('quant_state.json', {})
    trades = quant.get('trades', [])
    
    logs = []
    # Recent trades
    for t in trades[-10:]:
        action = t.get('action', {})
        if isinstance(action, dict):
            action = action.get('action', 'UNKNOWN')
        logs.append({
            'time': t.get('timestamp', ''),
            'type': 'TRADE',
            'message': f"{action} ${t.get('size', 0):.0f} on {t.get('question', '')[:30]}..."
        })
    
    # Add cycle info
    logs.append({
        'time': datetime.now(timezone.utc).isoformat(),
        'type': 'STATUS',
        'message': f"Cycle {quant.get('cycle', 0)} completed"
    })
    
    return jsonify({'logs': logs})

@app.route('/api/strategies')
def api_strategies():
    """Strategy performance data"""
    quant = load_json('quant_state.json', {})
    trades = quant.get('trades', [])
    
    # Group by strategy
    strat_data = {}
    for t in trades:
        s = t.get('strategy', 'UNKNOWN')
        if s not in strat_data:
            strat_data[s] = {'count': 0, 'total_edge': 0, 'total_size': 0}
        strat_data[s]['count'] += 1
        strat_data[s]['total_edge'] += t.get('edge', 0)
        strat_data[s]['total_size'] += t.get('size', 0)
    
    # Calculate averages
    for s in strat_data:
        if strat_data[s]['count'] > 0:
            strat_data[s]['avg_edge'] = strat_data[s]['total_edge'] / strat_data[s]['count']
            strat_data[s]['avg_size'] = strat_data[s]['total_size'] / strat_data[s]['count']
    
    return jsonify({'strategies': strat_data})

if __name__ == '__main__':
    print("=" * 50)
    print("Enhanced Data API: http://localhost:5002")
    print("=" * 50)
    app.run(debug=False, port=5002, host='0.0.0.0')