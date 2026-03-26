import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from loguru import logger

from ..config import get_config
from ..logging_utils import get_logger
from .models import (
    Market, Trade, Position, DailyMetrics, Review,
    ResearchCache, ForecastCache, TradeProposal, Forecast
)


class DatabaseRepository:
    def __init__(self, db_path: Optional[str] = None):
        config = get_config()
        self.db_path = db_path or config.DB_PATH
        self.logger = get_logger("repository")
        self._init_db()
    
    def _get_connection(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)
    
    @contextmanager
    def _transaction(self):
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        with self._transaction() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS markets (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    question TEXT,
                    description TEXT,
                    category TEXT,
                    outcomes TEXT,
                    volume_24h REAL DEFAULT 0,
                    liquidity REAL DEFAULT 0,
                    end_date TEXT,
                    resolved INTEGER DEFAULT 0,
                    winner TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    market_title TEXT,
                    order_id TEXT,
                    strategy TEXT,
                    side TEXT,
                    outcome TEXT,
                    size REAL DEFAULT 0,
                    price REAL DEFAULT 0,
                    cost REAL DEFAULT 0,
                    pnl REAL DEFAULT 0,
                    reasoning TEXT,
                    status TEXT DEFAULT 'PENDING',
                    simulated INTEGER DEFAULT 1,
                    created_at TEXT,
                    resolved_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    market_title TEXT,
                    outcome TEXT,
                    shares REAL DEFAULT 0,
                    avg_price REAL DEFAULT 0,
                    cost REAL DEFAULT 0,
                    current_value REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE,
                    total_pnl REAL DEFAULT 0,
                    trade_count INTEGER DEFAULT 0,
                    win_count INTEGER DEFAULT 0,
                    loss_count INTEGER DEFAULT 0,
                    total_exposure REAL DEFAULT 0,
                    largest_win REAL DEFAULT 0,
                    largest_loss REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    created_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_start TEXT,
                    period_end TEXT,
                    total_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    report_json TEXT,
                    parameter_changes TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS research_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT,
                    query TEXT,
                    research_json TEXT,
                    created_at TEXT,
                    expires_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS forecast_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT,
                    forecast_json TEXT,
                    confidence TEXT,
                    created_at TEXT,
                    expires_at TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_trades_market ON trades(market_id);
                CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);
                CREATE INDEX IF NOT EXISTS idx_positions_market ON positions(market_id);
                CREATE INDEX IF NOT EXISTS idx_research_market ON research_cache(market_id);
                CREATE INDEX IF NOT EXISTS idx_forecast_market ON forecast_cache(market_id);
            """)
    
    def save_market(self, market: Market) -> bool:
        try:
            with self._transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO markets 
                    (id, title, question, description, category, outcomes, volume_24h, 
                     liquidity, end_date, resolved, winner, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    market.id, market.title, market.question, market.description,
                    market.category, market.outcomes, market.volume_24h, market.liquidity,
                    market.end_date, int(market.resolved), market.winner,
                    market.created_at, datetime.now().isoformat()
                ))
            return True
        except Exception as e:
            self.logger.error(f"Failed to save market: {e}")
            return False
    
    def get_market(self, market_id: str) -> Optional[Dict]:
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM markets WHERE id = ?", (market_id,)).fetchone()
            return dict(row) if row else None
    
    def get_open_markets(self, limit: int = 100) -> List[Dict]:
        with self._transaction() as conn:
            rows = conn.execute("""
                SELECT * FROM markets WHERE resolved = 0 
                ORDER BY volume_24h DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def save_trade(self, trade: Trade) -> bool:
        try:
            with self._transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO trades 
                    (id, market_id, market_title, order_id, strategy, side, outcome, 
                     size, price, cost, pnl, reasoning, status, simulated, created_at, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.id, trade.market_id, trade.market_title, trade.order_id,
                    trade.strategy, trade.side, trade.outcome, trade.size, trade.price,
                    trade.cost, trade.pnl, trade.reasoning, trade.status, int(trade.simulated),
                    trade.created_at, trade.resolved_at
                ))
            return True
        except Exception as e:
            self.logger.error(f"Failed to save trade: {e}")
            return False
    
    def get_trades(
        self,
        market_id: Optional[str] = None,
        status: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict]:
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if market_id:
            query += " AND market_id = ?"
            params.append(market_id)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if days:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            query += " AND created_at >= ?"
            params.append(cutoff)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with self._transaction() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    
    def get_open_trades(self) -> List[Dict]:
        with self._transaction() as conn:
            rows = conn.execute("""
                SELECT * FROM trades WHERE status = 'FILLED' 
                ORDER BY created_at DESC
            """).fetchall()
            return [dict(row) for row in rows]
    
    def save_position(self, position: Position) -> bool:
        try:
            with self._transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO positions 
                    (id, market_id, market_title, outcome, shares, avg_price, 
                     cost, current_value, unrealized_pnl, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    position.id, position.market_id, position.market_title,
                    position.outcome, position.shares, position.avg_price,
                    position.cost, position.current_value, position.unrealized_pnl,
                    position.created_at, datetime.now().isoformat()
                ))
            return True
        except Exception as e:
            self.logger.error(f"Failed to save position: {e}")
            return False
    
    def get_positions(self, market_id: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM positions WHERE shares > 0"
        params = []
        
        if market_id:
            query += " AND market_id = ?"
            params.append(market_id)
        
        with self._transaction() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    
    def get_total_exposure(self) -> float:
        with self._transaction() as conn:
            result = conn.execute("""
                SELECT SUM(current_value) as total FROM positions WHERE shares > 0
            """).fetchone()
            return result["total"] if result else 0.0
    
    def get_portfolio_value(self) -> float:
        with self._transaction() as conn:
            result = conn.execute("""
                SELECT SUM(cost) as total FROM trades WHERE status IN ('FILLED', 'SETTLED')
            """).fetchone()
            return result["total"] if result else 0.0
    
    def get_daily_pnl(self, date: Optional[str] = None) -> float:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        with self._transaction() as conn:
            result = conn.execute("""
                SELECT SUM(pnl) as total FROM trades 
                WHERE date(created_at) = date(?) AND status = 'SETTLED'
            """, (date,)).fetchone()
            return float(result["total"]) if result and result["total"] is not None else 0.0
    
    def get_win_rate(self, days: int = 30) -> float:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._transaction() as conn:
            total = conn.execute("""
                SELECT COUNT(*) as count FROM trades 
                WHERE status = 'SETTLED' AND created_at >= ?
            """, (cutoff,)).fetchone()
            
            wins = conn.execute("""
                SELECT COUNT(*) as count FROM trades 
                WHERE status = 'SETTLED' AND pnl > 0 AND created_at >= ?
            """, (cutoff,)).fetchone()
            
            total_count = total["count"] if total else 0
            win_count = wins["count"] if wins else 0
            
            return win_count / total_count if total_count > 0 else 0.0
    
    def save_review(self, review: Review) -> int:
        try:
            with self._transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO reviews 
                    (period_start, period_end, total_trades, win_rate, total_pnl, 
                     report_json, parameter_changes, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    review.period_start, review.period_end, review.total_trades,
                    review.win_rate, review.total_pnl, review.report_json,
                    review.parameter_changes, review.status, review.created_at
                ))
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Failed to save review: {e}")
            return -1
    
    def get_reviews(self, limit: int = 10) -> List[Dict]:
        with self._transaction() as conn:
            rows = conn.execute("""
                SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def cache_research(self, market_id: str, query: str, research: Dict) -> bool:
        try:
            expires = (datetime.now() + timedelta(hours=24)).isoformat()
            with self._transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_cache 
                    (market_id, query, research_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (market_id, query, json.dumps(research), datetime.now().isoformat(), expires))
            return True
        except Exception as e:
            self.logger.error(f"Failed to cache research: {e}")
            return False
    
    def get_cached_research(self, market_id: str) -> Optional[Dict]:
        with self._transaction() as conn:
            row = conn.execute("""
                SELECT * FROM research_cache 
                WHERE market_id = ? AND expires_at > ?
                ORDER BY created_at DESC LIMIT 1
            """, (market_id, datetime.now().isoformat())).fetchone()
            
            if row:
                return json.loads(row["research_json"])
        return None
    
    def cache_forecast(self, market_id: str, forecast: Dict, confidence: str) -> bool:
        try:
            expires = (datetime.now() + timedelta(hours=6)).isoformat()
            with self._transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO forecast_cache 
                    (market_id, forecast_json, confidence, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (market_id, json.dumps(forecast), confidence, datetime.now().isoformat(), expires))
            return True
        except Exception as e:
            self.logger.error(f"Failed to cache forecast: {e}")
            return False
    
    def get_cached_forecast(self, market_id: str) -> Optional[Dict]:
        with self._transaction() as conn:
            row = conn.execute("""
                SELECT * FROM forecast_cache 
                WHERE market_id = ? AND expires_at > ?
                ORDER BY created_at DESC LIMIT 1
            """, (market_id, datetime.now().isoformat())).fetchone()
            
            if row:
                return json.loads(row["forecast_json"])
        return None
    
    def update_trade_pnl(self, trade_id: str, pnl: float, status: str = "SETTLED") -> bool:
        try:
            with self._transaction() as conn:
                conn.execute("""
                    UPDATE trades SET pnl = ?, status = ?, resolved_at = ?
                    WHERE id = ?
                """, (pnl, status, datetime.now().isoformat(), trade_id))
            return True
        except Exception as e:
            self.logger.error(f"Failed to update trade PnL: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        with self._transaction() as conn:
            total_trades = conn.execute("SELECT COUNT(*) as count FROM trades").fetchone()
            total_pnl = conn.execute("SELECT SUM(pnl) as total FROM trades WHERE status = 'SETTLED'").fetchone()
            open_positions = conn.execute("SELECT COUNT(*) as count FROM positions WHERE shares > 0").fetchone()
            exposure = conn.execute("SELECT SUM(current_value) as total FROM positions WHERE shares > 0").fetchone()
            
            return {
                "total_trades": total_trades["count"] if total_trades else 0,
                "total_pnl": total_pnl["total"] if total_pnl and total_pnl["total"] else 0.0,
                "open_positions": open_positions["count"] if open_positions else 0,
                "total_exposure": exposure["total"] if exposure and exposure["total"] else 0.0
            }


def get_repository(db_path: Optional[str] = None) -> DatabaseRepository:
    return DatabaseRepository(db_path)
