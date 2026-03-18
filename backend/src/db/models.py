"""
Database models for ArbitrageIQ.
Uses SQLite via SQLAlchemy — no external DB needed.
"""

import os
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, DateTime, Boolean, JSON,
    Integer, Text, create_engine, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'arbitrageiq.db')
DATABASE_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class MarketPrice(Base):
    """Stores normalized price snapshots from all sources."""
    __tablename__ = "market_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    market_id = Column(String, nullable=False)
    event_name = Column(String, nullable=False, default="")
    outcome = Column(String, nullable=False, default="yes")
    implied_probability = Column(Float, nullable=True)
    raw_odds = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    category = Column(String, default="other")
    metadata_ = Column("metadata", JSON, default=dict)
    is_active = Column(Boolean, default=True)
    # Extra columns used by ingestion modules
    market_title = Column(String, nullable=True)
    yes_price = Column(Float, nullable=True)
    no_price = Column(Float, nullable=True)
    last_traded_price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    open_interest = Column(Float, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_market_source_id", "source", "market_id"),
        Index("idx_market_category", "category"),
        Index("idx_market_timestamp", "timestamp"),
    )


class ArbOpportunity(Base):
    """Detected arbitrage opportunities."""
    __tablename__ = "arb_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_name = Column(String, nullable=False)
    category = Column(String, default="sports")
    profit_pct = Column(Float, nullable=False)
    legs = Column(JSON, nullable=False)
    total_stake_base = Column(Float, default=1000.0)
    profit_on_base = Column(Float)
    detected_at = Column(DateTime, default=datetime.utcnow)
    expired_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    opening_line = Column(JSON, nullable=True)
    closing_line = Column(JSON, nullable=True)


class Discrepancy(Base):
    """Detected discrepancies between market prices and public data."""
    __tablename__ = "discrepancies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, nullable=False)
    source = Column(String, nullable=False)
    event_name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    market_probability = Column(Float, nullable=False)
    data_implied_probability = Column(Float, nullable=False)
    edge_pct = Column(Float, nullable=False)
    direction = Column(String, nullable=False)
    data_source = Column(String, nullable=True)
    data_value = Column(Float, nullable=True)
    data_unit = Column(String, nullable=True)
    confidence = Column(String, default="medium")
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)


class TrackedMarket(Base):
    """All markets being monitored, with their data source mappings."""
    __tablename__ = "tracked_markets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    market_id = Column(String, nullable=False, unique=True)
    event_name = Column(String, nullable=False, default="")
    market_title = Column(String, nullable=True)
    category = Column(String, default="other")
    data_sources = Column(JSON, default=list)
    is_mapped = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)
    resolution_criteria = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)


class AlertLog(Base):
    """Log of all alerts sent."""
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String, nullable=False)
    market_id = Column(String, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    message_preview = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    # Extra fields used by telegram module
    channel = Column(String, nullable=True)
    title = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    recipient = Column(String, nullable=True)
    status = Column(String, default="sent")
    error_message = Column(Text, nullable=True)


class SystemStatus(Base):
    """Tracks last successful fetch per data source."""
    __tablename__ = "system_status"

    source = Column(String, primary_key=True)
    component = Column(String, nullable=True)
    last_success = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    credits_remaining = Column(Integer, nullable=True)
    markets_tracked = Column(Integer, default=0)
    status = Column(String, default="unknown")
    consecutive_failures = Column(Integer, default=0)
    metadata_ = Column("metadata", JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Create all tables. Call on startup."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Yield a scoped database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {os.path.abspath(DB_PATH)}")
