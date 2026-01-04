"""
SQLAlchemy Models for HedgeBot
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, Text, ForeignKey
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
    symbol = Column(String(20), default="BTC/USDT")
    
    # API Keys (encrypted in production)
    api_key_a = Column(String(255), nullable=True)
    api_secret_a = Column(String(255), nullable=True)
    api_key_b = Column(String(255), nullable=True)
    api_secret_b = Column(String(255), nullable=True)
    
    # Trading parameters
    leverage = Column(Integer, default=1)
    order_type = Column(Enum(OrderType), default=OrderType.MARKET)
    position_size_usdt = Column(Float, default=100.0)  # Fixed size in USDT
    position_size_percent = Column(Float, nullable=True)  # Or % of balance
    
    # Risk management
    stop_loss_percent = Column(Float, default=2.0)  # Global stop-loss %
    take_profit_percent = Column(Float, default=5.0)  # Global take-profit %
    max_daily_loss = Column(Float, default=500.0)  # Max daily loss in USDT
    
    # Entry triggers
    spread_threshold = Column(Float, default=0.5)  # Min spread % for entry
    
    # Fees for simulation
    taker_fee = Column(Float, default=0.1)  # 0.1%
    maker_fee = Column(Float, default=0.05)  # 0.05%
    slippage = Column(Float, default=0.05)  # 0.05% estimated slippage
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    trades = relationship("Trade", back_populates="config")


class Trade(Base):
    """Individual trade/position record"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("bot_configs.id"), nullable=False)
    
    # Trade identification
    trade_id = Column(String(100), unique=True, index=True)  # UUID
    status = Column(Enum(TradeStatus), default=TradeStatus.OPEN)
    mode = Column(Enum(TradingMode), default=TradingMode.SIMULATION)
    
    # Symbol and exchanges
    symbol = Column(String(20), nullable=False)
    exchange_a = Column(String(50), nullable=False)  # Long side
    exchange_b = Column(String(50), nullable=False)  # Short side
    
    # Entry data
    entry_price_a = Column(Float, nullable=False)  # Long entry price
    entry_price_b = Column(Float, nullable=False)  # Short entry price
    entry_amount = Column(Float, nullable=False)  # Position size in base currency
    entry_amount_usdt = Column(Float, nullable=False)  # Position size in USDT
    leverage = Column(Integer, default=1)
    
    open_time = Column(DateTime(timezone=True), server_default=func.now())
    
    # Exit data (filled on close)
    exit_price_a = Column(Float, nullable=True)
    exit_price_b = Column(Float, nullable=True)
    close_time = Column(DateTime(timezone=True), nullable=True)
    
    # PnL calculations
    pnl_a = Column(Float, default=0.0)  # PnL from long position
    pnl_b = Column(Float, default=0.0)  # PnL from short position
    pnl_net = Column(Float, default=0.0)  # Total PnL after fees
    fees_paid = Column(Float, default=0.0)  # Total fees
    
    # Current prices (updated in real-time for open positions)
    current_price_a = Column(Float, nullable=True)
    current_price_b = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    
    # Close reason
    close_reason = Column(String(50), nullable=True)  # stop_loss, take_profit, manual, panic
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    config = relationship("BotConfig", back_populates="trades")


class Log(Base):
    """System and trading logs"""
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    
    level = Column(String(20), default="INFO")  # INFO, WARNING, ERROR, DEBUG
    category = Column(String(50), default="system")  # system, trade, risk, api
    message = Column(Text, nullable=False)
    
    # Optional context
    trade_id = Column(String(100), nullable=True)
    config_id = Column(Integer, nullable=True)
    extra_data = Column(Text, nullable=True)  # JSON string for additional data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
