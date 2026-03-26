#!/usr/bin/env python3
"""
Script to run the Polymarket trading bot in paper trading mode.
This simulates trades without actually placing orders on the blockchain.
"""

import sys
import asyncio
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import and run the main function
from polymarket_ai_bot.main import main

if __name__ == "__main__":
    # Ensure we're in paper mode
    os.environ["BOT_MODE"] = "paper"
    
    print("Starting Polymarket Trading Bot in PAPER TRADING mode")
    print("=" * 50)
    print("This simulates trades without real money at risk.")
    print("To switch to live trading, set BOT_MODE=live in .env")
    print("=" * 50)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error running bot: {e}")
        sys.exit(1)