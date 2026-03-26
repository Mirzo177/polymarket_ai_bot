#!/usr/bin/env python3
"""
PROFESSIONAL MARKET ANALYST ENGINE
Bloomberg-level analysis with technical indicators, sentiment, and event tracking
"""
import os
import json
import time
import uuid
import math
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass

os.environ['POLY_BUILDER_KEY'] = '019d2b2f-b867-7daf-ac0b-92da916743fd'
os.environ['POLY_BUILDER_SECRET'] = 'g8_tldos1eNeC1Ri6Itnaz49ibSBRCQKhYQCgK30qos='
os.environ['POLY_BUILDER_PASSPHRASE'] = 'bd017fc2ea140a60e42763d2383935fa6dd33b0d972ba08f7bf96d0c5cc41059'

from polymarket_apis import PolymarketGammaClient
import httpx


# ==================== TECHNICAL INDICATORS ====================

class TechnicalAnalyst:
    """Professional technical analysis with Bloomberg-style indicators"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=30)
    
    def analyze(self, price_history: List[float]) -> Dict:
        """Comprehensive technical analysis"""
        if len(price_history) < 5:
            return self._neutral_analysis()
        
        prices = np.array(price_history)
        
        return {
            'rsi': self._calculate_rsi(prices),
            'macd': self._calculate_macd(prices),
            'bollinger': self._calculate_bollinger(prices),
            'moving_averages': self._calculate_moving_averages(prices),
            'trend': self._determine_trend(prices),
            'volatility': self._calculate_volatility(prices),
            'momentum': self._calculate_momentum(prices)
        }
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> Dict:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return {'value': 50, 'signal': 'neutral'}
        
        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            rs = 100
        else:
            rs = avg_gain / avg_loss
        
        rsi = 100 - (100 / (1 + rs))
        
        signal = 'oversold' if rsi < 30 else 'overbought' if rsi > 70 else 'neutral'
        
        return {'value': round(rsi, 1), 'signal': signal}
    
    def _calculate_macd(self, prices: np.ndarray) -> Dict:
        """MACD (Moving Average Convergence Divergence)"""
        if len(prices) < 26:
            return {'macd': 0, 'signal': 'neutral', 'histogram': 0}
        
        # EMA calculations
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        
        macd_line = ema12 - ema26
        signal_line = self._ema(np.array([macd_line]), 9)
        histogram = macd_line - signal_line
        
        if len(prices) >= 35:
            prev_macd = self._ema(prices[:-9], 12) - self._ema(prices[:-9], 26)
            prev_signal = self._ema(np.array([prev_macd]), 9)
            cross = 'bullish' if macd_line > signal_line and prev_macd < prev_signal else 'bearish' if macd_line < signal_line and prev_macd > prev_signal else 'none'
        else:
            cross = 'neutral'
        
        return {
            'macd': round(macd_line, 4),
            'signal_line': round(signal_line, 4),
            'histogram': round(histogram, 4),
            'cross': cross
        }
    
    def _ema(self, prices: np.ndarray, period: int) -> float:
        """Exponential Moving Average"""
        if len(prices) < period:
            return np.mean(prices)
        
        alpha = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = alpha * p + (1 - alpha) * ema
        return ema
    
    def _calculate_bollinger(self, prices: np.ndarray, period: int = 20) -> Dict:
        """Bollinger Bands"""
        if len(prices) < period:
            return {'upper': 0, 'middle': 0, 'lower': 0, 'position': 'neutral'}
        
        recent = prices[-period:]
        middle = np.mean(recent)
        std = np.std(recent)
        
        upper = middle + (2 * std)
        lower = middle - (2 * std)
        
        current = prices[-1]
        
        if current > upper:
            position = 'overbought'
        elif current < lower:
            position = 'oversold'
        else:
            position = 'neutral'
        
        bandwidth = (upper - lower) / middle if middle > 0 else 0
        
        return {
            'upper': round(upper, 4),
            'middle': round(middle, 4),
            'lower': round(lower, 4),
            'position': position,
            'bandwidth': round(bandwidth, 4)
        }
    
    def _calculate_moving_averages(self, prices: np.ndarray) -> Dict:
        """Moving Averages (SMA and EMA)"""
        ma = {}
        
        for period in [5, 10, 20, 50]:
            if len(prices) >= period:
                ma[f'sma_{period}'] = round(np.mean(prices[-period:]), 4)
                ma[f'ema_{period}'] = round(self._ema(prices, period), 4)
        
        # Golden/Death cross detection
        if 'sma_50' in ma and 'sma_20' in ma:
            ma['golden_cross'] = ma['sma_50'] < ma['sma_20']  # 50 above 20 = bullish
            ma['death_cross'] = ma['sma_50'] > ma['sma_20']
        
        return ma
    
    def _determine_trend(self, prices: np.ndarray) -> Dict:
        """Determine overall trend"""
        if len(prices) < 10:
            return {'direction': 'neutral', 'strength': 0}
        
        # Linear regression for trend
        x = np.arange(len(prices))
        slope, intercept = np.polyfit(x, prices, 1)
        
        # Normalize slope
        avg_price = np.mean(prices)
        normalized_slope = (slope / avg_price) * 100 if avg_price > 0 else 0
        
        direction = 'bullish' if normalized_slope > 0.5 else 'bearish' if normalized_slope < -0.5 else 'neutral'
        strength = min(abs(normalized_slope) * 10, 100)
        
        return {'direction': direction, 'strength': round(strength, 1), 'slope': round(normalized_slope, 4)}
    
    def _calculate_volatility(self, prices: np.ndarray) -> Dict:
        """Volatility metrics"""
        if len(prices) < 5:
            return {'daily': 0, 'annualized': 0, 'level': 'low'}
        
        returns = np.diff(prices) / prices[:-1]
        daily_vol = np.std(returns) if len(returns) > 0 else 0
        annualized_vol = daily_vol * math.sqrt(365)
        
        level = 'low' if annualized_vol < 0.3 else 'medium' if annualized_vol < 0.6 else 'high'
        
        return {
            'daily': round(daily_vol * 100, 2),
            'annualized': round(annualized_vol * 100, 1),
            'level': level
        }
    
    def _calculate_momentum(self, prices: np.ndarray) -> Dict:
        """Momentum indicators"""
        if len(prices) < 10:
            return {'score': 0, 'signal': 'neutral'}
        
        # ROC (Rate of Change)
        roc = ((prices[-1] - prices[-10]) / prices[-10] * 100) if prices[-10] != 0 else 0
        
        score = 50 + (roc * 2)  # Normalize to 0-100
        score = max(0, min(100, score))
        
        signal = 'strong_buy' if score > 70 else 'buy' if score > 55 else 'strong_sell' if score < 30 else 'sell' if score < 45 else 'neutral'
        
        return {'score': round(score, 1), 'roc': round(roc, 2), 'signal': signal}
    
    def _neutral_analysis(self) -> Dict:
        """Return neutral analysis when insufficient data"""
        return {
            'rsi': {'value': 50, 'signal': 'neutral'},
            'macd': {'macd': 0, 'signal': 'neutral', 'histogram': 0},
            'bollinger': {'upper': 0, 'middle': 0, 'lower': 0, 'position': 'neutral'},
            'moving_averages': {},
            'trend': {'direction': 'neutral', 'strength': 0},
            'volatility': {'daily': 0, 'annualized': 0, 'level': 'low'},
            'momentum': {'score': 50, 'signal': 'neutral'}
        }


# ==================== SENTIMENT ANALYST ====================

class SentimentAnalyst:
    """Bloomberg-level sentiment analysis from multiple sources"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=30)
    
    def analyze(self, question: str, news_items: List[Dict]) -> Dict:
        """Comprehensive sentiment analysis"""
        
        # Extract key entities and topics
        topics = self._extract_topics(question)
        
        # Analyze news sentiment
        news_sentiment = self._analyze_news_sentiment(news_items)
        
        # Social sentiment (simulated - would integrate Twitter/Reddit)
        social_sentiment = self._analyze_social_sentiment(topics)
        
        # Aggregate sentiment
        overall = self._aggregate_sentiment(news_sentiment, social_sentiment)
        
        return {
            'topics': topics,
            'news_sentiment': news_sentiment,
            'social_sentiment': social_sentiment,
            'overall': overall,
            'sentiment_score': overall['score'],
            'confidence': overall['confidence']
        }
    
    def _extract_topics(self, question: str) -> List[str]:
        """Extract key topics from question"""
        question = question.lower()
        topics = []
        
        # Sports
        if any(w in question for w in ['nhl', 'stanley', 'hockey']):
            topics.append('sports_hockey')
        if any(w in question for w in ['nba', 'basketball']):
            topics.append('sports_basketball')
        if any(w in question for w in ['world cup', 'fifa', 'soccer']):
            topics.append('sports_soccer')
        if any(w in question for w in ['super bowl', 'nfl', 'football']):
            topics.append('sports_football')
        
        # Politics
        if any(w in question for w in ['trump', 'biden', 'president', 'election']):
            topics.append('politics_us')
        
        # Crypto
        if any(w in question for w in ['bitcoin', 'btc', 'crypto', 'ethereum']):
            topics.append('crypto')
        
        # Tech/Gaming
        if any(w in question for w in ['gta', 'game', 'apple', 'microsoft']):
            topics.append('tech_gaming')
        
        return topics if topics else ['general']
    
    def _analyze_news_sentiment(self, news: List[Dict]) -> Dict:
        """Analyze news articles for sentiment"""
        if not news:
            return {'score': 50, 'signal': 'neutral', 'articles': 0}
        
        bullish = 0
        bearish = 0
        neutral = 0
        
        for item in news:
            title = item.get('title', '').lower()
            
            bullish_words = ['up', 'rise', 'gain', 'bullish', 'positive', 'growth', 'win', 'success', ' rally', 'surge', 'soar']
            bearish_words = ['down', 'fall', 'drop', 'bearish', 'negative', 'decline', 'lose', 'fail', 'crash', 'plunge']
            
            if any(w in title for w in bullish_words):
                bullish += 1
            elif any(w in title for w in bearish_words):
                bearish += 1
            else:
                neutral += 1
        
        total = len(news)
        score = 50 + ((bullish - bearish) / total * 50) if total > 0 else 50
        
        signal = 'bullish' if score > 60 else 'bearish' if score < 40 else 'neutral'
        
        return {
            'score': round(score, 1),
            'signal': signal,
            'articles': total,
            'bullish': bullish,
            'bearish': bearish
        }
    
    def _analyze_social_sentiment(self, topics: List[str]) -> Dict:
        """Analyze social media sentiment (simulated)"""
        # In production, would integrate Twitter/Reddit APIs
        return {'score': 50, 'signal': 'neutral', 'sources': 0}
    
    def _aggregate_sentiment(self, news: Dict, social: Dict) -> Dict:
        """Combine news and social sentiment"""
        # Weight news more heavily
        score = (news['score'] * 0.7) + (social['score'] * 0.3)
        
        confidence = min(100, (news.get('articles', 0) * 10) + 30)
        
        return {
            'score': round(score, 1),
            'signal': 'bullish' if score > 60 else 'bearish' if score < 40 else 'neutral',
            'confidence': round(confidence, 1)
        }


# ==================== EVENT CATALOG ====================

class EventCalendar:
    """Track upcoming events and catalysts"""
    
    def __init__(self):
        self.events = self._load_default_events()
    
    def _load_default_events(self) -> List[Dict]:
        """Load known upcoming events"""
        now = datetime.now(timezone.utc)
        return [
            {'name': 'GTA VI Release', 'date': '2025-09-01', 'type': 'entertainment', 'impact': 'high'},
            {'name': '2026 FIFA World Cup', 'date': '2026-06-01', 'type': 'sports', 'impact': 'high'},
            {'name': 'NHL Stanley Cup Finals', 'date': '2026-06-01', 'type': 'sports', 'impact': 'medium'},
            {'name': '2026 NBA Finals', 'date': '2026-06-01', 'type': 'sports', 'impact': 'medium'},
            {'name': 'US Presidential Election', 'date': '2026-11-01', 'type': 'politics', 'impact': 'high'},
        ]
    
    def get_upcoming(self, days: int = 30) -> List[Dict]:
        """Get events in next N days"""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)
        
        upcoming = []
        for e in self.events:
            event_date_str = e['date']
            if 'Z' in event_date_str:
                event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
            else:
                event_date = datetime.fromisoformat(event_date_str).replace(tzinfo=timezone.utc)
            
            if now <= event_date <= cutoff:
                e['days_until'] = (event_date - now).days
                upcoming.append(e)
        
        return sorted(upcoming, key=lambda x: x['days_until'])
    
    def find_related_events(self, question: str) -> List[Dict]:
        """Find events related to a market question"""
        question = question.lower()
        related = []
        
        for e in self.events:
            if e['name'].lower() in question or any(t in question for t in e['type'].split('_')):
                related.append(e)
        
        return related


# ==================== CORRELATION ANALYZER ====================

class CorrelationAnalyzer:
    """Analyze market correlations and patterns"""
    
    def __init__(self):
        self.history = {}
    
    def analyze_market_correlations(self, markets: List[Any]) -> Dict:
        """Find correlated markets"""
        
        # Group by category
        categories = defaultdict(list)
        for m in markets:
            cat = self._categorize(m.question)
            categories[cat].append(m)
        
        # Find potential correlations
        correlations = {}
        
        for cat, cat_markets in categories.items():
            if len(cat_markets) > 1:
                correlations[cat] = {
                    'count': len(cat_markets),
                    'markets': [m.question[:40] for m in cat_markets[:5]],
                    'correlation_type': 'same_category'
                }
        
        return correlations
    
    def _categorize(self, question: str) -> str:
        """Categorize market"""
        q = question.lower()
        
        if any(w in q for w in ['gta', 'game', 'release']):
            return 'gaming'
        elif any(w in q for w in ['nhl', 'stanley', 'hockey']):
            return 'hockey'
        elif any(w in q for w in ['nba', 'basketball']):
            return 'basketball'
        elif any(w in q for w in ['world cup', 'fifa', 'soccer']):
            return 'soccer'
        elif any(w in q for w in ['bitcoin', 'btc', 'crypto']):
            return 'crypto'
        elif any(w in q for w in ['trump', 'president', 'election']):
            return 'politics'
        
        return 'other'


# ==================== ANALYST REPORT GENERATOR ====================

class AnalystReport:
    """Generate Bloomberg-style analyst reports"""
    
    def __init__(self):
        self.technical = TechnicalAnalyst()
        self.sentiment = SentimentAnalyst()
        self.events = EventCalendar()
        self.correlation = CorrelationAnalyzer()
    
    def generate_report(self, market: Any, price_history: List[float], news: List[Dict]) -> Dict:
        """Generate comprehensive analyst report"""
        
        # Technical analysis
        technical = self.technical.analyze(price_history)
        
        # Sentiment analysis
        sentiment = self.sentiment.analyze(market.question, news)
        
        # Event calendar
        related_events = self.events.find_related_events(market.question)
        upcoming = self.events.get_upcoming(30)
        
        # Price and volume
        price_yes = market.outcome_prices[0] if market.outcome_prices else 0.5
        volume = market.volume_24hr or 0
        liquidity = market.liquidity or 0
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            technical, sentiment, price_yes, related_events
        )
        
        # Risk assessment
        risk = self._assess_risk(technical, sentiment, liquidity)
        
        return {
            'market': {
                'id': market.id,
                'question': market.question,
                'price_yes': price_yes,
                'price_no': market.outcome_prices[1] if market.outcome_prices and len(market.outcome_prices) > 1 else 0.5,
                'volume_24h': volume,
                'liquidity': liquidity
            },
            'technical': technical,
            'sentiment': sentiment,
            'events': {
                'related': related_events[:3],
                'upcoming': upcoming[:5]
            },
            'recommendation': recommendation,
            'risk': risk,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def _generate_recommendation(self, technical: Dict, sentiment: Dict, price: float, events: List[Dict]) -> Dict:
        """Generate trading recommendation"""
        
        score = 50  # Neutral baseline
        
        # Technical signals
        if technical['trend']['direction'] == 'bullish':
            score += 10
        elif technical['trend']['direction'] == 'bearish':
            score -= 10
        
        if technical['momentum']['signal'] in ['strong_buy', 'buy']:
            score += 15
        elif technical['momentum']['signal'] in ['strong_sell', 'sell']:
            score -= 15
        
        if technical['rsi']['signal'] == 'oversold':
            score += 10
        elif technical['rsi']['signal'] == 'overbought':
            score -= 10
        
        # Sentiment
        if sentiment['overall']['signal'] == 'bullish':
            score += 15
        elif sentiment['overall']['signal'] == 'bearish':
            score -= 15
        
        # Events
        if events:
            for e in events:
                if e.get('days_until', 999) < 7:
                    score += 5  # Near-term catalyst
        
        # Clamp score
        score = max(0, min(100, score))
        
        action = 'BUY' if score > 65 else 'SELL' if score < 35 else 'HOLD'
        confidence = abs(score - 50) / 50 * 100
        
        return {
            'action': action,
            'score': round(score, 1),
            'confidence': round(confidence, 1),
            'rationale': self._generate_rationale(technical, sentiment, events)
        }
    
    def _generate_rationale(self, technical: Dict, sentiment: Dict, events: List[Dict]) -> str:
        """Generate recommendation rationale"""
        parts = []
        
        # Technical
        if technical['trend']['direction'] != 'neutral':
            parts.append(f"Trend: {technical['trend']['direction']}")
        
        if technical['momentum']['signal'] != 'neutral':
            parts.append(f"Momentum: {technical['momentum']['signal']}")
        
        # Sentiment
        if sentiment['overall']['signal'] != 'neutral':
            parts.append(f"Sentiment: {sentiment['overall']['signal']}")
        
        # Events
        if events:
            parts.append(f"Events: {len(events)} related")
        
        return " | ".join(parts) if parts else "No clear signals"
    
    def _assess_risk(self, technical: Dict, sentiment: Dict, liquidity: float) -> Dict:
        """Assess market risk"""
        
        risk_score = 50
        
        # Volatility risk
        if technical['volatility']['level'] == 'high':
            risk_score += 20
        elif technical['volatility']['level'] == 'low':
            risk_score -= 10
        
        # Sentiment confidence
        if sentiment['overall']['confidence'] < 40:
            risk_score += 15
        
        # Liquidity risk
        if liquidity < 10000:
            risk_score += 20
        elif liquidity > 100000:
            risk_score -= 15
        
        risk_score = max(0, min(100, risk_score))
        
        level = 'low' if risk_score < 30 else 'medium' if risk_score < 60 else 'high'
        
        return {
            'score': round(risk_score, 1),
            'level': level,
            'factors': self._identify_risk_factors(technical, sentiment, liquidity)
        }
    
    def _identify_risk_factors(self, technical: Dict, sentiment: Dict, liquidity: float) -> List[str]:
        """Identify specific risk factors"""
        factors = []
        
        if technical['volatility']['level'] == 'high':
            factors.append('High volatility')
        
        if liquidity < 10000:
            factors.append('Low liquidity')
        
        if sentiment['overall']['confidence'] < 40:
            factors.append('Low sentiment confidence')
        
        if technical['rsi']['signal'] in ['oversold', 'overbought']:
            factors.append(f"RSI at {technical['rsi']['signal']}")
        
        return factors if factors else ['None identified']


# ==================== MAIN ANALYST ENGINE ====================

class ProfessionalAnalyst:
    """Bloomberg-level market analysis engine"""
    
    def __init__(self):
        self.gamma = PolymarketGammaClient()
        self.client = httpx.Client(timeout=30)
        self.report_generator = AnalystReport()
    
    def analyze_market(self, market: Any, fetch_price_history: bool = True) -> Dict:
        """Full professional analysis of a market"""
        
        # Get price history (simulated - would need WebSocket for real-time)
        price_history = self._get_price_history(market.id) if fetch_price_history else []
        
        # Get news
        news = self._search_news(market.question)
        
        # Generate report
        report = self.report_generator.generate_report(market, price_history, news)
        
        return report
    
    def analyze_all_markets(self, min_volume: float = 50000) -> List[Dict]:
        """Analyze top markets"""
        
        markets = self.gamma.get_markets(limit=50, closed=False)
        
        # Filter by volume
        liquid = [m for m in markets if (m.volume_24hr or 0) > min_volume]
        liquid.sort(key=lambda x: x.volume_24hr or 0, reverse=True)
        
        # Analyze top 15
        results = []
        for m in liquid[:15]:
            report = self.analyze_market(m)
            results.append(report)
        
        return results
    
    def _get_price_history(self, market_id: str) -> List[float]:
        """Get price history (simulated)"""
        # In production, would use WebSocket or historical API
        # Simulate some price movement
        import random
        base = 0.5
        return [base + random.uniform(-0.1, 0.1) for _ in range(20)]
    
    def _search_news(self, query: str) -> List[Dict]:
        """Search for related news"""
        try:
            # Use Google News RSS
            terms = query.split()[:3]
            search = '+'.join(terms)
            url = f"https://news.google.com/rss/search?q={search}&hl=en-US&gl=US&ceid=US:en"
            
            resp = self.client.get(f"https://api.rss2json.com/v1/api.json?rssurl={url}&count=5")
            
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {'title': item.get('title', ''), 'link': item.get('link', '')}
                    for item in data.get('items', [])
                ]
        except:
            pass
        
        return []
    
    def generate_top_opportunities(self, min_score: int = 60) -> List[Dict]:
        """Find best opportunities based on analyst recommendations"""
        
        analyses = self.analyze_all_markets()
        
        opportunities = []
        for a in analyses:
            rec = a.get('recommendation', {})
            if rec.get('score', 0) >= min_score:
                opportunities.append(a)
        
        # Sort by score
        opportunities.sort(key=lambda x: x['recommendation']['score'], reverse=True)
        
        return opportunities
    
    def run_analysis_cycle(self) -> Dict:
        """Run complete analysis cycle"""
        
        print("\n" + "="*70)
        print("PROFESSIONAL ANALYST CYCLE")
        print("="*70)
        
        # Get opportunities
        opportunities = self.generate_top_opportunities()
        
        print(f"[ANALYSIS] {len(opportunities)} opportunities identified")
        
        # Show top 5
        for i, opp in enumerate(opportunities[:5]):
            m = opp['market']
            rec = opp['recommendation']
            
            print(f"\n{i+1}. {m['question'][:50]}...")
            print(f"   Price: ${m['price_yes']:.2f} | Vol: ${m['volume_24h']:,.0f}")
            print(f"   RECOMMENDATION: {rec['action']} (Score: {rec['score']})")
            print(f"   Rationale: {rec['rationale']}")
            print(f"   Risk: {opp['risk']['level']} ({opp['risk']['score']})")
        
        return {
            'opportunities': opportunities,
            'total_analyzed': len(opportunities)
        }


if __name__ == "__main__":
    analyst = ProfessionalAnalyst()
    result = analyst.run_analysis_cycle()
    print(f"\n[DONE] Found {result['total_analyzed']} opportunities")