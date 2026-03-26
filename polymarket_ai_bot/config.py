import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class GlobalConfig(BaseModel):
    polling_interval_sec: int = 60
    log_level: str = "INFO"
    max_markets_per_cycle: int = 10
    base_currency: str = "USD"
    time_zone: str = "UTC"
    max_text_tokens: int = 8000


class RiskConfig(BaseModel):
    max_notional_per_market: float = 100.0
    max_total_exposure: float = 500.0
    max_daily_loss_pct: float = 5.0
    max_position_per_outcome: float = 50.0
    stop_trading_on_drawdown: bool = True
    min_edge_threshold: float = 0.05
    min_liquidity_usd: float = 1000.0


class ValueBetConfig(BaseModel):
    min_edge: float = 0.05
    kelly_fraction: float = 0.25
    max_bet_pct_portfolio: float = 0.05


class TrendFollowConfig(BaseModel):
    ma_short: int = 20
    ma_long: int = 50
    rsi_oversold: int = 30
    rsi_overbought: int = 70


class SimpleArbConfig(BaseModel):
    min_price_deviation: float = 0.02
    max_position_size: float = 25.0


class StrategiesConfig(BaseModel):
    value_bet: ValueBetConfig = Field(default_factory=ValueBetConfig)
    trend_follow: TrendFollowConfig = Field(default_factory=TrendFollowConfig)
    simple_arb: SimpleArbConfig = Field(default_factory=SimpleArbConfig)


class ResearchConfig(BaseModel):
    max_articles: int = 5
    max_news_sources: int = 3
    max_text_tokens_to_send: int = 6000
    news_timeout_sec: int = 30


class ExecutionConfig(BaseModel):
    order_timeout_sec: int = 30
    max_retries: int = 3
    retry_delay_sec: int = 5


class Settings(BaseModel):
    global_settings: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    risk: RiskConfig = Field(default_factory=RiskConfig)
    strategies: StrategiesConfig = Field(default_factory=StrategiesConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)


class Config:
    _instance: Optional['Config'] = None
    
    def __init__(self):
        load_dotenv()
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        self.POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
        self.POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
        self.BOT_WALLET_PRIVATE_KEY = os.getenv("BOT_WALLET_PRIVATE_KEY", "")
        self.BOT_WALLET_ADDRESS = os.getenv("BOT_WALLET_ADDRESS", "")
        self.BOT_MODE = os.getenv("BOT_MODE", "paper").lower()
        self.DB_PATH = os.getenv("DB_PATH", "./polymarket_ai_bot/db.sqlite")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
        self.TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
        
        config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
                self.settings = Settings(**data)
        else:
            self.settings = Settings()
        
        self.IS_LIVE_MODE = self.BOT_MODE == "live"
    
    @classmethod
    def get_instance(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance
    
    @classmethod
    def reload(cls) -> 'Config':
        cls._instance = Config()
        return cls._instance


def get_config() -> Config:
    return Config.get_instance()
