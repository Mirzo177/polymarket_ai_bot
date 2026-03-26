from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField


class Market(SQLModel, table=True):
    __tablename__ = "markets"
    
    id: str = SQLField(primary_key=True)
    title: str = SQLField(index=True)
    question: str = ""
    description: str = ""
    category: str = ""
    outcomes: str = ""
    volume_24h: float = 0.0
    liquidity: float = 0.0
    end_date: Optional[str] = None
    resolved: bool = False
    winner: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Trade(SQLModel, table=True):
    __tablename__ = "trades"
    
    id: str = SQLField(primary_key=True)
    market_id: str = SQLField(index=True)
    market_title: str = ""
    order_id: str = ""
    strategy: str = ""
    side: str = ""
    outcome: str = ""
    size: float = 0.0
    price: float = 0.0
    cost: float = 0.0
    pnl: float = 0.0
    reasoning: str = ""
    status: str = "PENDING"
    simulated: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None
    
    
class Position(SQLModel, table=True):
    __tablename__ = "positions"
    
    id: str = SQLField(primary_key=True)
    market_id: str = SQLField(index=True)
    market_title: str = ""
    outcome: str = ""
    shares: float = 0.0
    avg_price: float = 0.0
    cost: float = 0.0
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class DailyMetrics(SQLModel, table=True):
    __tablename__ = "daily_metrics"
    
    id: int = SQLField(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    date: str = Field(index=True)
    total_pnl: float = 0.0
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_exposure: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Review(SQLModel, table=True):
    __tablename__ = "reviews"
    
    id: int = SQLField(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    period_start: str = ""
    period_end: str = ""
    total_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    report_json: str = ""
    parameter_changes: str = ""
    status: str = "PENDING"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ResearchCache(SQLModel, table=True):
    __tablename__ = "research_cache"
    
    id: int = SQLField(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    market_id: str = SQLField(index=True)
    query: str = ""
    research_json: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""


class ForecastCache(SQLModel, table=True):
    __tablename__ = "forecast_cache"
    
    id: int = SQLField(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    market_id: str = SQLField(index=True)
    forecast_json: str = ""
    confidence: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""


class TradeProposal(BaseModel):
    market_id: str
    market_title: str
    action: str
    outcome: str
    size: float
    price: float
    expected_value: float
    edge: float
    confidence: str
    reasoning: str
    strategy: str


class Forecast(BaseModel):
    market_id: str
    outcomes: List[dict]
    summary: str
    market_sentiment: str
    key_factors: List[str]
    confidence: str


class ResearchResult(BaseModel):
    market_id: str
    query: str
    key_facts: List[str]
    bull_case: str
    bear_case: str
    market_relevance: str
    confidence: str
    sources: List[str]


class RiskAssessment(BaseModel):
    approved: bool
    risk_score: float
    reasons: List[str]
    size_reduction_pct: float = 0.0
    conditional_notes: str = ""


class MarketCandidate(BaseModel):
    market_id: str
    title: str
    category: str
    volume_24h: float
    liquidity: float
    time_to_resolve: str
    potential_edge: str
    priority_score: float
    outcomes: List[dict] = []
    market_price: dict = {}
