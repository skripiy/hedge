"""
Pydantic Schemas for API validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# Enums for API
class TradingMode(str, Enum):
    SIMULATION = "simulation"
    LIVE = "live"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class BotStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


# ============ Config Schemas ============

class ConfigBase(BaseModel):
    name: str = "Default Strategy"
    mode: TradingMode = TradingMode.SIMULATION
    
    virtual_balance: float = 10000.0
    
    exchange_a: str = "binance"
    exchange_b: str = "bybit"
    
    max_daily_loss: float = Field(default=500.0, ge=0)
    
    taker_fee: float = Field(default=0.05, ge=0)
    maker_fee: float = Field(default=0.02, ge=0)
    slippage: float = Field(default=0.02, ge=0)
    
    # Volume Farming fields
    strategy_mode: str = "volume_break_even"
    min_hold_time_minutes: int = 60
    max_hold_time_minutes: int = 480
    use_maker_orders: bool = False


class ConfigCreate(ConfigBase):
    api_key_a: Optional[str] = None
    api_secret_a: Optional[str] = None
    api_key_b: Optional[str] = None
    api_secret_b: Optional[str] = None


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[TradingMode] = None
    virtual_balance: Optional[float] = None
    exchange_a: Optional[str] = None
    exchange_b: Optional[str] = None
    max_daily_loss: Optional[float] = None
    taker_fee: Optional[float] = None
    maker_fee: Optional[float] = None
    slippage: Optional[float] = None
    # Volume Farming fields
    strategy_mode: Optional[str] = None
    min_hold_time_minutes: Optional[int] = None
    max_hold_time_minutes: Optional[int] = None
    use_maker_orders: Optional[bool] = None
    # API Keys
    api_key_a: Optional[str] = None
    api_secret_a: Optional[str] = None
    api_key_b: Optional[str] = None
    api_secret_b: Optional[str] = None


class ConfigResponse(ConfigBase):
    id: int
    status: BotStatus
    current_balance: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Hide API secrets in response
    has_api_keys_a: bool = False
    has_api_keys_b: bool = False
    
    class Config:
        from_attributes = True


# ============ Trade Schemas ============

class TradeBase(BaseModel):
    symbol: str
    exchange_a: str
    exchange_b: str
    entry_price_a: float
    entry_price_b: float
    entry_amount: float
    entry_amount_usdt: float
    leverage: int = 1


class TradeCreate(TradeBase):
    config_id: int
    mode: TradingMode = TradingMode.SIMULATION


class TradeResponse(TradeBase):
    id: int
    trade_id: str
    config_id: int
    status: TradeStatus
    mode: TradingMode
    
    open_time: datetime
    close_time: Optional[datetime] = None
    
    exit_price_a: Optional[float] = None
    exit_price_b: Optional[float] = None
    
    pnl_a: float = 0.0
    pnl_b: float = 0.0
    pnl_net: float = 0.0
    fees_paid: float = 0.0
    
    current_price_a: Optional[float] = None
    current_price_b: Optional[float] = None
    unrealized_pnl: float = 0.0
    
    close_reason: Optional[str] = None
    
    class Config:
        from_attributes = True


class TradeCloseRequest(BaseModel):
    reason: str = "manual"  # manual, panic, stop_loss, take_profit


# ============ Status Schemas ============

class BotStatusResponse(BaseModel):
    status: BotStatus
    mode: TradingMode
    current_balance: float
    unrealized_pnl: float
    total_pnl_today: float
    open_positions_count: int
    uptime_seconds: Optional[int] = None
    last_activity: Optional[datetime] = None
    
    # Per-exchange info
    exchange_a: str = "binance"
    exchange_b: str = "bybit"
    balance_a: float = 0.0
    balance_b: float = 0.0
    
    # Connection status
    exchange_a_connected: bool = False
    exchange_b_connected: bool = False
    database_connected: bool = True


class PositionSummary(BaseModel):
    trade_id: str
    symbol: str
    exchange_a: str
    exchange_b: str
    side_a: str = "long"
    side_b: str = "short"
    entry_price_a: float
    entry_price_b: float
    current_price_a: Optional[float]
    current_price_b: Optional[float]
    amount_usdt: float
    pnl_a: float
    pnl_b: float
    total_pnl: float
    open_time: datetime


# ============ Log Schemas ============

class LogCreate(BaseModel):
    level: str = "INFO"
    category: str = "system"
    message: str
    trade_id: Optional[str] = None
    config_id: Optional[int] = None
    extra_data: Optional[str] = None


class LogResponse(BaseModel):
    id: int
    level: str
    category: str
    message: str
    trade_id: Optional[str] = None
    config_id: Optional[int] = None
    extra_data: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Action Schemas ============

class StartBotRequest(BaseModel):
    config_id: int = 1


class StopBotRequest(BaseModel):
    config_id: int = 1
    close_positions: bool = False  # Whether to close all open positions


class PanicCloseRequest(BaseModel):
    config_id: int = 1


class ActionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
