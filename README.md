# Polymarket AI Trading Bot

A sophisticated, locally-run Polymarket trading agent that operates 24/7 with the capabilities of a 20+ year professional trader. Built with Python and powered by Claude API for intelligent market analysis and decision making.

## Features

- **Multi-Agent Architecture**: Specialized agents for scanning, research, forecasting, trading, risk management, and review
- **24/7 Autonomous Operation**: Continuously monitors markets and executes trades
- **Professional-Grade Analysis**: Combines quantitative strategies with LLM-powered qualitative analysis
- **Risk-First Design**: Paper trading mode by default with comprehensive risk controls
- **Self-Improvement**: Performance review system that suggests parameter and code improvements
- **Local-First**: Everything runs on your machine - no external dependencies or VPS required
- **Multiple Strategies**: Value betting, trend following, and arbitrage approaches

## System Overview

The bot implements a multi-agent system where each agent has a specific role:

1. **ScannerAgent** - Identifies promising markets based on liquidity, volume, and timing
2. **ResearchAgent** - Gathers and synthesizes relevant news and information
3. **ForecasterAgent** - Generates calibrated probability estimates for market outcomes
4. **TraderAgent** - Converts forecasts into trade proposals using professional strategies
5. **RiskManagerAgent** - Enforces strict risk limits and portfolio controls
6. **ReviewerAgent** - Analyzes performance and suggests improvements

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository (assuming you already have the files)
cd polymarket_ai_bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example config files
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
```

### 2. Configure Environment

Edit `.env` file to add your Anthropic API key:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
# Other optional keys:
# POLYMARKET_API_KEY=your_key_if_needed
# BOT_MODE=paper  # Default is paper trading
```

### 3. Run in Paper Trading Mode (Recommended for Testing)

```bash
python scripts/run_paper_trading.py
```

### 4. Switch to Live Trading (When Ready)

**WARNING**: Only do this after thorough testing in paper mode!

1. Change `BOT_MODE=live` in your `.env` file
2. Ensure you have sufficient funds in your Polymarket wallet
3. Run: `python scripts/run_live_trading.py`

### 5. Run Performance Reviews

```bash
python scripts/run_evaluation.py
```

## Project Structure

```
polymarket_ai_bot/
├── polymarket_ai_bot/              # Main package
│   ├── agents/                     # All AI agents
│   │   ├── scanner_agent.py        # Market scanning
│   │   ├── research_agent.py       # News/research gathering
│   │   ├── forecaster_agent.py     # Probability forecasting
│   │   ├── trader_agent.py         # Trade proposal generation
│   │   ├── risk_manager_agent.py   # Risk management
│   │   └── reviewer_agent.py       # Performance review
│   ├── clients/                    # External API clients
│   │   ├── polymarket_client.py    # Polymarket API wrapper
│   │   ├── web_search_client.py    # News search
│   │   └── price_client.py         # Price data (CoinGecko)
│   ├── data_store/                 # Data persistence layer
│   │   ├── models.py               # Database schemas
│   │   └── repository.py           # Data access layer
│   ├── llm/                        # LLM interface
│   │   ├── claude_client.py        # Claude API wrapper
│   │   └── prompts.py              # Expert agent prompts
│   ├── strategies/                 # Trading strategies
│   │   ├── value_bet.py            # Kelly criterion betting
│   │   ├── trend_follow.py         # Trend following
│   │   └── simple_arb.py           # Arbitrage detection
│   ├── tools/                      # Utility functions
│   │   ├── portfolio_utils.py      # Portfolio calculations
│   │   ├── backtest.py             # Strategy backtesting
│   │   └── metrics.py              # Performance metrics
│   ├── main.py                     # Main orchestration loop
│   ├── config.py                   # Configuration management
│   └── logging_utils.py            # Logging setup
├── scripts/                        # Entry point scripts
│   ├── run_paper_trading.py        # Paper trading mode
│   ├── run_live_trading.py         # Live trading mode
│   └── run_evaluation.py           # Performance review
├── config/                         # Configuration files
│   └── settings.yaml               # Strategy and risk parameters
├── .env.example                    # Environment variables template
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## Configuration

### Environment Variables (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | API key for Claude | (required) |
| `POLYMARKET_API_KEY` | Polymarket API key (if needed) |  |
| `POLYGON_RPC_URL` | Polygon RPC URL | `https://polygon-rpc.com` |
| `BOT_WALLET_PRIVATE_KEY` | Wallet private key for live trading |  |
| `BOT_WALLET_ADDRESS` | Wallet address |  |
| `BOT_MODE` | Trading mode: `paper` or `live` | `paper` |
| `DB_PATH` | SQLite database path | `./polymarket_ai_bot/db.sqlite` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Strategy Settings (config/settings.yaml)

Adjust parameters in `config/settings.yaml` to tune strategy behavior:

- **Risk Management**: Position sizes, daily loss limits, exposure limits
- **Strategies**: Value bet thresholds, trend following parameters
- **Research**: News sources, article limits
- **Execution**: Polling intervals, timeouts

## Safety Features

- **Paper Trading Default**: Bot starts in simulation mode - no real money at risk
- **Explicit Live Switch**: Must consciously change `BOT_MODE=live` to trade real funds
- **Comprehensive Risk Controls**: Position limits, daily loss limits, exposure controls
- **No Key Logging**: API keys and private keys are never logged
- **Human-in-the-Loop Review**: Performance improvements require manual approval
- **Dry-Run Execution**: All order simulation before live execution

## Strategies Implemented

### 1. Value Betting Strategy
- Compares forecasted probabilities vs market odds
- Uses fractional Kelly criterion for optimal bet sizing
- Only bets when edge exceeds configurable threshold

### 2. Trend Following Strategy
- Uses moving averages and RSI for crypto-correlated markets
- Combines technical indicators with LLM narrative validation
- Adjusts position size based on trend strength

### 3. Simple Arbitrage Strategy
- Detects mispriced complementary markets
- Seeks risk-free profits from pricing inefficiencies
- Currently runs in simulation mode for safety

## Performance & Review System

The bot continuously learns and improves:

1. **Trade Logging**: Every decision is recorded with reasoning
2. **Outcome Tracking**: P&L calculated when markets resolve
3. **Periodic Reviews**: Automated performance analysis
4. **LLM-Powered Insights**: Claude identifies mistake patterns
5. **Actionable Suggestions**: Parameter adjustments and code improvements
6. **Manual Approval**: All changes require human verification

## Requirements

- Python 3.11+
- Anthropic API key (for Claude access)
- Internet connection (for API calls)
- Windows/Linux/macOS (tested on Windows WSL and Ubuntu)

## Dependencies

See `requirements.txt` for full list:
- anthropic: Claude API access
- python-dotenv: Environment variable management
- pydantic/pydantic-settings: Configuration validation
- sqlmodel: Database ORM
- loguru: Structured logging
- requests/httpx: HTTP clients
- tenacity: Retry logic

## Development & Customization

### Adding New Strategies
1. Create a new file in `strategies/` directory
2. Implement your strategy logic
3. Integrate with `TraderAgent.run_step()`
4. Add configuration parameters to `settings.yaml`

### Modifying Agent Behavior
1. Edit the system prompts in `llm/prompts.py`
2. Adjust agent logic in respective agent files
3. Tune parameters in `config/settings.yaml`

### Extending Data Sources
1. Add new client in `clients/` directory
2. Integrate with `ResearchAgent` or other relevant agents
3. Update data flow in `main.py`

## Disclaimer

⚠️ **IMPORTANT**: Trading involves risk, including the potential loss of principal. This software is for educational and informational purposes only. Past performance is not indicative of future results. The developers are not financial advisors and do not guarantee profits. Always trade responsibly and never risk more than you can afford to lose.

- Start with paper trading to validate strategies
- Begin with small position sizes when going live
- Monitor the bot regularly, especially during volatile market conditions
- Never leave the bot running unattended without proper risk controls

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with inspiration from professional trading practices
- Utilizes public APIs from Polymarket, CoinGecko, and news sources
- Powered by Anthropic's Claude API for intelligent decision making
- Created for educational purposes to demonstrate AI-agent trading systems