#!/usr/bin/env python3
"""
Test script to verify the basic structure and imports work correctly.
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all modules can be imported without errors."""
    print("Testing imports...")
    
    try:
        from polymarket_ai_bot.config import get_config
        print("[OK] Config imported successfully")
    except Exception as e:
        print(f"[FAIL] Config import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.llm.claude_client import ClaudeClient
        print("[OK] Claude client imported successfully")
    except Exception as e:
        print(f"[FAIL] Claude client import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.clients.polymarket_client import PolymarketClient
        print("[OK] Polymarket client imported successfully")
    except Exception as e:
        print(f"[FAIL] Polymarket client import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.clients.web_search_client import WebSearchClient
        print("[OK] Web search client imported successfully")
    except Exception as e:
        print(f"[FAIL] Web search client import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.clients.price_client import PriceClient
        print("[OK] Price client imported successfully")
    except Exception as e:
        print(f"[FAIL] Price client import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.data_store.repository import DatabaseRepository
        print("[OK] Repository imported successfully")
    except Exception as e:
        print(f"[FAIL] Repository import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.agents.scanner_agent import ScannerAgent
        print("[OK] Scanner agent imported successfully")
    except Exception as e:
        print(f"[FAIL] Scanner agent import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.agents.research_agent import ResearchAgent
        print("[OK] Research agent imported successfully")
    except Exception as e:
        print(f"[FAIL] Research agent import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.agents.forecaster_agent import ForecasterAgent
        print("[OK] Forecaster agent imported successfully")
    except Exception as e:
        print(f"[FAIL] Forecaster agent import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.agents.trader_agent import TraderAgent
        print("[OK] Trader agent imported successfully")
    except Exception as e:
        print(f"[FAIL] Trader agent import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.agents.risk_manager_agent import RiskManagerAgent
        print("[OK] Risk manager agent imported successfully")
    except Exception as e:
        print(f"[FAIL] Risk manager agent import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.agents.reviewer_agent import ReviewerAgent
        print("[OK] Reviewer agent imported successfully")
    except Exception as e:
        print(f"[FAIL] Reviewer agent import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.strategies.value_bet import ValueBetStrategy
        print("[OK] Value bet strategy imported successfully")
    except Exception as e:
        print(f"[FAIL] Value bet strategy import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.strategies.trend_follow import TrendFollowStrategy
        print("[OK] Trend follow strategy imported successfully")
    except Exception as e:
        print(f"[FAIL] Trend follow strategy import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.strategies.simple_arb import SimpleArbitrageStrategy
        print("[OK] Simple arbitrage strategy imported successfully")
    except Exception as e:
        print(f"[FAIL] Simple arbitrage strategy import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.tools.portfolio_utils import PortfolioUtils
        print("[OK] Portfolio utils imported successfully")
    except Exception as e:
        print(f"[FAIL] Portfolio utils import failed: {e}")
        return False
    
    try:
        from polymarket_ai_bot.tools.backtest import BacktestEngine
        print("[OK] Backtest engine imported successfully")
    except Exception as e:
        print(f"[FAIL] Backtest engine import failed: {e}")
        return False
    
    print("\nAll imports successful! [OK]")
    return True

def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        from polymarket_ai_bot.config import get_config
        config = get_config()
        print(f"[OK] Config loaded successfully")
        print(f"  - Bot mode: {config.BOT_MODE}")
        print(f"  - DB path: {config.DB_PATH}")
        print(f"  - Live mode: {config.IS_LIVE_MODE}")
        return True
    except Exception as e:
        print(f"[FAIL] Config test failed: {e}")
        return False

if __name__ == "__main__":
    print("Polymarket Trading Bot - Import Test")
    print("=" * 40)
    
    success = test_imports()
    if success:
        success = test_config()
    
    if success:
        print("\n[SUCCESS] All tests passed! The bot structure is ready.")
        sys.exit(0)
    else:
        print("\n[FAILURE] Some tests failed. Please check the errors above.")
        sys.exit(1)