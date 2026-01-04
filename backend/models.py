"""
SQLAlchemy Models for HedgeBot
Multi-symbol support with Decision Log
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
import enum


class TradingMode(str, enum.Enum):
    SIMULATION = "simulation"
    LIVE = "live"


class OrderSide(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"


class TradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class BotStatus(str, enum.Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class DecisionType(str, enum.Enum):
    SCAN = "scan"           # Regular price scan
    OPPORTUNITY = "opportunity"  # Found entry opportunity
    ENTRY = "entry"         # Entered position
    SKIP = "skip"           # Skipped opportunity (reason in message)
    EXIT = "exit"           # Exited position
    RISK = "risk"           # Risk check
    ERROR = "error"         # Error occurred


class BotConfig(Base):
    """Bot configuration stored in database"""
    __tablename__ = "bot_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), default="Default Strategy")
    
    # Trading mode
    mode = Column(Enum(TradingMode), default=TradingMode.SIMULATION)
    status = Column(Enum(BotStatus), default=BotStatus.STOPPED)
    
    # Virtual balance for simulation
    virtual_balance = Column(Float, default=10000.0)
    current_balance = Column(Float, default=10000.0)
    
    # Exchange settings
    exchange_a = Column(String(50), default="binance")
    exchange_b = Column(String(50), default="bybit")
    
    # API Keys (encrypted in production)
    api_key_a = Column(String(255), nullable=True)
    api_secret_a = Column(String(255), nullable=True)
    api_key_b = Column(String(255), nullable=True)
    api_secret_b = Column(String(255), nullable=True)
    
    # Global risk management
    max_daily_loss = Column(Float, default=500.0)
    
    # Fees for simulation
    taker_fee = Column(Float, default=0.1)
    maker_fee = Column(Float, default=0.05)
    slippage = Column(Float, default=0.05)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    trades = relationship("Trade", back_populates="config")
    symbols = relationship("SymbolConfig", back_populates="config")


class SymbolConfig(Base):
    """Per-symbol trading configuration"""
    __tablename__ = "symbol_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("bot_configs.id"), nullable=False)
    
    # Symbol settings
    symbol = Column(String(20), nullable=False)  # e.g., BTC/USDT
    enabled = Column(Boolean, default=True)
    
    # Trading parameters
    leverage = Column(Integer, default=1)
    order_type = Column(Enum(OrderType), default=OrderType.MARKET)
    position_size_usdt = Column(Float, default=100.0)
    position_size_percent = Column(Float, nullable=True)
    
    # Entry triggers
    spread_threshold = Column(Float, default=0.5)  # Min spread % for entry
    
    # Risk management per symbol
    stop_loss_percent = Column(Float, default=2.0)
    take_profit_percent = Column(Float, default=5.0)
    max_positions = Column(Integer, default=1)  # Max concurrent positions for this symbol
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    config = relationship("BotConfig", back_populates="symbols")


class Trade(Base):
    """Individual trade/position record"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("bot_configs.id"), nullable=False)
    
    # Trade identification
    trade_id = Column(String(100), unique=True, index=True)
    status = Column(Enum(TradeStatus), default=TradeStatus.OPEN)
    mode = Column(Enum(TradingMode), default=TradingMode.SIMULATION)
    
    # Symbol and exchanges
    symbol = Column(String(20), nullable=False)
    exchange_a = Column(String(50), nullable=False)
    exchange_b = Column(String(50), nullable=False)
    
    # Entry data
    entry_price_a = Column(Float, nullable=False)
    entry_price_b = Column(Float, nullable=False)
    entry_amount = Column(Float, nullable=False)
    entry_amount_usdt = Column(Float, nullable=False)
    leverage = Column(Integer, default=1)
    
    open_time = Column(DateTime(timezone=True), server_default=func.now())
    
    # Exit data
    exit_price_a = Column(Float, nullable=True)
    exit_price_b = Column(Float, nullable=True)
    close_time = Column(DateTime(timezone=True), nullable=True)
    
    # PnL
    pnl_a = Column(Float, default=0.0)
    pnl_b = Column(Float, default=0.0)
    pnl_net = Column(Float, default=0.0)
    fees_paid = Column(Float, default=0.0)
    
    # Current prices
    current_price_a = Column(Float, nullable=True)
    current_price_b = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    
    close_reason = Column(String(50), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    config = relationship("BotConfig", back_populates="trades")


class Decision(Base):
    """Bot decision/thought process log"""
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, nullable=True)
    
    # Decision details
    decision_type = Column(Enum(DecisionType), default=DecisionType.SCAN)
    symbol = Column(String(20), nullable=False)
    
    # Market data at decision time
    price_a = Column(Float, nullable=True)  # Price on exchange A
    price_b = Column(Float, nullable=True)  # Price on exchange B
    spread = Column(Float, nullable=True)   # Spread %
    spread_threshold = Column(Float, nullable=True)  # Required spread
    
    # Decision outcome
    action_taken = Column(String(50), nullable=True)  # entered, skipped, closed, etc.
    reason = Column(Text, nullable=True)  # Why this decision was made
    
    # Additional context
    position_id = Column(String(100), nullable=True)
    pnl = Column(Float, nullable=True)
    extra_data = Column(JSON, nullable=True)  # Additional metrics
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Log(Base):
    """System and trading logs"""
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    
    level = Column(String(20), default="INFO")
    category = Column(String(50), default="system")
    message = Column(Text, nullable=False)
    
    trade_id = Column(String(100), nullable=True)
    config_id = Column(Integer, nullable=True)
    extra_data = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PriceCache(Base):
    """Cached prices for quick access"""
    __tablename__ = "price_cache"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    exchange = Column(String(50), nullable=False)
    
    bid = Column(Float, nullable=True)
    ask = Column(Float, nullable=True)
    last = Column(Float, nullable=True)
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
