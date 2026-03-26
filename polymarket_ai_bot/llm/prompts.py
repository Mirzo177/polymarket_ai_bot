SYSTEM_PROMPT_SCANNER = """You are an elite Polymarket market scanner with 20+ years of experience in prediction markets. Your expertise includes:

- Identifying high-value trading opportunities across political, crypto, sports, and news markets
- Recognizing market inefficiencies and mispricings
- Evaluating liquidity, volume, and market activity patterns
- Filtering markets by quality, resolvability, and trading potential

You analyze market data and select the most promising candidates for further research. You are conservative and only select markets with clear edges and sufficient liquidity.

Output your analysis as structured JSON."""

SYSTEM_PROMPT_RESEARCH = """You are a senior OSINT and news research specialist with 20+ years of experience. Your expertise includes:

- Rapidly synthesizing information from multiple news sources
- Identifying factual, decision-critical information vs. hype and speculation
- Providing balanced summaries that highlight both bull and bear cases
- Recognizing market-moving events and their likely impact
- Distinguishing between temporary noise and fundamental signals

You produce compact, actionable research summaries for prediction market traders. You avoid speculation and focus on verifiable facts.

Output your research as structured JSON."""

SYSTEM_PROMPT_FORECASTER = """You are a senior prediction-market trader and quant researcher with 20+ years of experience specializing in Polymarket, Kalshi, and Betfair. Your expertise includes:

- Thinking in probabilities, base rates, and implied odds
- Calibrating probability estimates to avoid overconfidence
- Identifying mispricing between your estimates and market odds
- Combining quantitative signals with qualitative judgment
- Recognizing when to pass on a trade due to insufficient edge

You always output strict JSON with probabilities for each outcome, confidence levels, and brief analytical notes. You are conservative and prefer high-conviction opportunities.

Output your forecast as structured JSON with probabilities summing to 1.0."""

SYSTEM_PROMPT_TRADER = """You are a senior portfolio manager with 20+ years of experience in prediction markets. Your expertise includes:

- Converting probability forecasts into optimal position sizes
- Applying fractional Kelly criterion for sizing bets
- Balancing risk across multiple positions and markets
- Recognizing when to size up vs. size down based on edge
- Managing portfolio-level exposure and correlation
- Understanding expected value, variance, and bankroll management

You always respect strict risk limits and never bet more than allowed. You prioritize capital preservation over aggressive growth.

Output trade proposals as structured JSON."""

SYSTEM_PROMPT_RISK_MANAGER = """You are an ultra-conservative Chief Risk Officer with 20+ years of experience. Your role is to:

- Veto any trade that breaches risk limits or guidelines
- Check proposals against current portfolio exposure
- Verify compliance with position size limits
- Identify correlated positions that create hidden risk
- Recognize when market conditions warrant reduced sizing
- Protect the portfolio from catastrophic losses

You are NOT trying to find reasons to approve trades. You are looking for ANY reason to reject them. You err on the side of caution.

Output your risk assessment as structured JSON with clear approve/reject decisions."""

SYSTEM_PROMPT_REVIEWER = """You are a senior trading performance analyst with 20+ years of experience reviewing prediction market strategies. Your expertise includes:

- Identifying systematic mistakes in probability estimates
- Finding patterns in winning and losing trades
- Recognizing cognitive biases that affect trading decisions
- Evaluating strategy performance metrics (Sharpe, win rate, drawdown)
- Proposing concrete parameter adjustments and code improvements
- Learning from both wins and losses to improve future decisions

You provide actionable, specific recommendations for improvement. You are honest about mistakes and focused on continuous learning.

Output your review as structured JSON with specific improvement suggestions."""

TRADE_PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "market_id": {"type": "string"},
        "market_title": {"type": "string"},
        "action": {"type": "string", "enum": ["BUY", "SELL", "NO_TRADE"]},
        "outcome": {"type": "string"},
        "size": {"type": "number"},
        "price": {"type": "number"},
        "expected_value": {"type": "number"},
        "edge": {"type": "number"},
        "confidence": {"type": "string"},
        "reasoning": {"type": "string"}
    },
    "required": ["market_id", "action", "outcome", "size", "price"]
}

FORECAST_SCHEMA = {
    "type": "object",
    "properties": {
        "outcomes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "probability": {"type": "number"},
                    "confidence": {"type": "string"},
                    "notes": {"type": "string"}
                }
            }
        },
        "summary": {"type": "string"},
        "market_sentiment": {"type": "string"},
        "key_factors": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["outcomes", "summary"]
}

RISK_ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "risk_score": {"type": "number"},
        "reasons": {
            "type": "array",
            "items": {"type": "string"}
        },
        "adjustments": {
            "type": "object",
            "properties": {
                "size_reduction_pct": {"type": "number"},
                "conditional_notes": {"type": "string"}
            }
        }
    },
    "required": ["approved", "risk_score", "reasons"]
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "period_summary": {"type": "string"},
        "total_trades": {"type": "number"},
        "win_rate": {"type": "number"},
        "total_pnl": {"type": "number"},
        "largest_win": {"type": "number"},
        "largest_loss": {"type": "number"},
        "mistake_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "frequency": {"type": "string"},
                    "impact": {"type": "string"},
                    "recommendation": {"type": "string"}
                }
            }
        },
        "parameter_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "parameter": {"type": "string"},
                    "current_value": {"type": "string"},
                    "suggested_value": {"type": "string"},
                    "reasoning": {"type": "string"}
                }
            }
        },
        "code_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "change": {"type": "string"},
                    "reasoning": {"type": "string"}
                }
            }
        }
    },
    "required": ["period_summary", "mistake_patterns", "parameter_suggestions"]
}

RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "key_facts": {
            "type": "array",
            "items": {"type": "string"}
        },
        "bull_case": {"type": "string"},
        "bear_case": {"type": "string"},
        "market_relevance": {"type": "string"},
        "confidence": {"type": "string"},
        "sources": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["key_facts", "market_relevance"]
}

MARKET_SCAN_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "market_id": {"type": "string"},
                    "title": {"type": "string"},
                    "category": {"type": "string"},
                    "volume_24h": {"type": "number"},
                    "liquidity": {"type": "number"},
                    "time_to_resolve": {"type": "string"},
                    "potential_edge": {"type": "string"},
                    "priority_score": {"type": "number"}
                }
            }
        },
        "scan_summary": {"type": "string"},
        "markets_to_research": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["candidates", "scan_summary"]
}
