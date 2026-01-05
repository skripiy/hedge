"""
Database Service for HedgeBot
Provides async database operations for the trading bot
"""
import os
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, and_
import logging

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://hedge_user:hedge_pass@localhost:5432/hedge_db"
)


class DatabaseService:
    """
    Async database service for bot operations.
    Handles saving trades, loading config, and logging.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        self.engine = None
        self.async_session = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Initialize database connection"""
        try:
            self.engine = create_async_engine(
                self.database_url,
                echo=os.getenv("DEBUG", "false").lower() == "true",
                pool_pre_ping=True
            )
            
            self.async_session = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            async with self.async_session() as session:
                await session.execute(select(1))
            
            self._connected = True
            logger.info("Database connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            self._connected = False
            logger.info("Database disconnected")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def _get_session(self) -> AsyncSession:
        """Get a new database session"""
        if not self.async_session:
            raise RuntimeError("Database not connected")
        return self.async_session()
    
    # ============ Config Operations ============
    
    async def load_config(self, config_id: int = 1) -> Optional[Dict[str, Any]]:
        """Load bot configuration from database"""
        try:
            async with self.async_session() as session:
                # Import here to avoid circular imports
                from backend.models import BotConfig
                
                result = await session.execute(
                    select(BotConfig).where(BotConfig.id == config_id)
                )
                config = result.scalar_one_or_none()
                
                if not config:
                    logger.warning(f"Config {config_id} not found, using defaults")
                    return None
                
                return {
                    "id": config.id,
                    "name": config.name,
                    "mode": config.mode.value if config.mode else "simulation",
                    "status": config.status.value if config.status else "stopped",
                    "virtual_balance": config.virtual_balance,
                    "current_balance": config.current_balance,
                    "exchange_a": config.exchange_a,
                    "exchange_b": config.exchange_b,
                    "api_key_a": getattr(config, 'api_key_a', None),
                    "api_secret_a": getattr(config, 'api_secret_a', None),
                    "api_key_b": getattr(config, 'api_key_b', None),
                    "api_secret_b": getattr(config, 'api_secret_b', None),
                    "max_daily_loss": config.max_daily_loss,
                    "taker_fee": config.taker_fee,
                    "maker_fee": config.maker_fee,
                    "slippage": config.slippage,
                    # Volume Farming settings
                    "strategy_mode": getattr(config, 'strategy_mode', 'hedge'),
                    "min_hold_time_minutes": getattr(config, 'min_hold_time_minutes', 60),
                    "max_hold_time_minutes": getattr(config, 'max_hold_time_minutes', 480),
                    "close_only_if_profitable": getattr(config, 'close_only_if_profitable', True),
                    "min_entry_spread_percent": getattr(config, 'min_entry_spread_percent', 0.30),
                    "target_daily_volume": getattr(config, 'target_daily_volume', 100000.0),
                    "max_concurrent_positions": getattr(config, 'max_concurrent_positions', 5),
                    "use_maker_orders": getattr(config, 'use_maker_orders', False),
                }
                
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return None
    
    async def update_config_status(self, config_id: int, status: str) -> bool:
        """Update bot status in config"""
        try:
            async with self.async_session() as session:
                from backend.models import BotConfig, BotStatus
                
                result = await session.execute(
                    select(BotConfig).where(BotConfig.id == config_id)
                )
                config = result.scalar_one_or_none()
                
                if config:
                    config.status = BotStatus(status)
                    await session.commit()
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error updating config status: {e}")
            return False
    
    async def update_balance(self, config_id: int, new_balance: float) -> bool:
        """Update current balance in config"""
        try:
            async with self.async_session() as session:
                from backend.models import BotConfig
                
                result = await session.execute(
                    select(BotConfig).where(BotConfig.id == config_id)
                )
                config = result.scalar_one_or_none()
                
                if config:
                    config.current_balance = new_balance
                    await session.commit()
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error updating balance: {e}")
            return False
    
    # ============ Trade Operations ============
    
    async def save_trade(
        self,
        config_id: int,
        position: 'HedgePosition',  # Forward reference
        mode: str = "simulation"
    ) -> Optional[str]:
        """Save a new trade to database"""
        try:
            async with self.async_session() as session:
                from backend.models import Trade, TradingMode, TradeStatus
                
                trade_id = str(uuid.uuid4())
                
                trade = Trade(
                    config_id=config_id,
                    trade_id=trade_id,
                    status=TradeStatus(position.status.value),
                    mode=TradingMode(mode),
                    symbol=position.symbol,
                    exchange_a=position.exchange_a,
                    exchange_b=position.exchange_b,
                    entry_price_a=position.entry_price_a,
                    entry_price_b=position.entry_price_b,
                    entry_amount=position.entry_amount,
                    entry_amount_usdt=position.entry_amount_usdt,
                    leverage=position.leverage,
                    open_time=position.open_time or datetime.utcnow(),
                    current_price_a=position.current_price_a,
                    current_price_b=position.current_price_b,
                    unrealized_pnl=position.unrealized_pnl,
                    fees_paid=position.fees_paid
                )
                
                session.add(trade)
                await session.commit()
                
                logger.info(f"Trade saved: {trade_id}")
                return trade_id
                
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
            return None
    
    async def create_trade_simple(
        self,
        config_id: int,
        symbol: str,
        exchange_a: str,
        exchange_b: str,
        entry_price_a: float,
        entry_price_b: float,
        amount: float,
        amount_usdt: float,
        leverage: int = 1,
        fees: float = 0.0,
        mode: str = "simulation"
    ) -> Optional[str]:
        """Create a new trade with simple params (for Volume Farming mode)"""
        try:
            async with self.async_session() as session:
                from backend.models import Trade, TradingMode, TradeStatus
                
                trade_id = str(uuid.uuid4())
                
                trade = Trade(
                    config_id=config_id,
                    trade_id=trade_id,
                    status=TradeStatus.OPEN,
                    mode=TradingMode(mode),
                    symbol=symbol,
                    exchange_a=exchange_a,
                    exchange_b=exchange_b,
                    entry_price_a=entry_price_a,
                    entry_price_b=entry_price_b,
                    entry_amount=amount,
                    entry_amount_usdt=amount_usdt,
                    leverage=leverage,
                    open_time=datetime.utcnow(),
                    current_price_a=entry_price_a,
                    current_price_b=entry_price_b,
                    unrealized_pnl=0.0,
                    fees_paid=fees,
                    volume_generated=amount_usdt * 2 * leverage
                )
                
                session.add(trade)
                await session.commit()
                
                logger.info(f"Trade created: {trade_id} for {symbol}")
                return trade_id
                
        except Exception as e:
            logger.error(f"Error creating trade: {e}")
            return None
    
    async def update_trade(
        self,
        trade_id: str,
        current_price_a: Optional[float] = None,
        current_price_b: Optional[float] = None,
        unrealized_pnl: Optional[float] = None,
        pnl_a: Optional[float] = None,
        pnl_b: Optional[float] = None
    ) -> bool:
        """Update trade with current prices and PnL"""
        try:
            async with self.async_session() as session:
                from backend.models import Trade
                
                result = await session.execute(
                    select(Trade).where(Trade.trade_id == trade_id)
                )
                trade = result.scalar_one_or_none()
                
                if trade:
                    if current_price_a is not None:
                        trade.current_price_a = current_price_a
                    if current_price_b is not None:
                        trade.current_price_b = current_price_b
                    if unrealized_pnl is not None:
                        trade.unrealized_pnl = unrealized_pnl
                    if pnl_a is not None:
                        trade.pnl_a = pnl_a
                    if pnl_b is not None:
                        trade.pnl_b = pnl_b
                    
                    await session.commit()
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error updating trade: {e}")
            return False
    
    async def close_trade(
        self,
        trade_id: str,
        exit_price_a: float,
        exit_price_b: float,
        pnl_a: float,
        pnl_b: float,
        pnl_net: float,
        fees_paid: float,
        close_reason: str
    ) -> bool:
        """Close a trade with final PnL"""
        try:
            async with self.async_session() as session:
                from backend.models import Trade, TradeStatus
                
                result = await session.execute(
                    select(Trade).where(Trade.trade_id == trade_id)
                )
                trade = result.scalar_one_or_none()
                
                if trade:
                    trade.status = TradeStatus.CLOSED
                    trade.exit_price_a = exit_price_a
                    trade.exit_price_b = exit_price_b
                    trade.pnl_a = pnl_a
                    trade.pnl_b = pnl_b
                    trade.pnl_net = pnl_net
                    trade.fees_paid = fees_paid
                    trade.close_reason = close_reason
                    trade.close_time = datetime.utcnow()
                    
                    await session.commit()
                    logger.info(f"Trade closed: {trade_id}, PnL: {pnl_net}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error closing trade: {e}")
            return False
    
    async def get_open_trades(self, config_id: int) -> List[Dict]:
        """Get all open trades for a config"""
        try:
            async with self.async_session() as session:
                from backend.models import Trade, TradeStatus
                
                result = await session.execute(
                    select(Trade).where(
                        and_(
                            Trade.config_id == config_id,
                            Trade.status == TradeStatus.OPEN
                        )
                    )
                )
                trades = result.scalars().all()
                
                return [
                    {
                        "trade_id": t.trade_id,
                        "symbol": t.symbol,
                        "exchange_a": t.exchange_a,
                        "exchange_b": t.exchange_b,
                        "entry_price_a": t.entry_price_a,
                        "entry_price_b": t.entry_price_b,
                        "entry_amount": t.entry_amount,
                        "entry_amount_usdt": t.entry_amount_usdt,
                        "open_time": t.open_time,
                        "unrealized_pnl": t.unrealized_pnl
                    }
                    for t in trades
                ]
                
        except Exception as e:
            logger.error(f"Error getting open trades: {e}")
            return []
    
    # ============ Log Operations ============
    
    async def log(
        self,
        level: str,
        category: str,
        message: str,
        config_id: Optional[int] = None,
        trade_id: Optional[str] = None,
        extra_data: Optional[Dict] = None
    ) -> bool:
        """Save a log entry to database"""
        try:
            async with self.async_session() as session:
                from backend.models import Log
                
                log_entry = Log(
                    level=level.upper(),
                    category=category,
                    message=message,
                    config_id=config_id,
                    trade_id=trade_id,
                    extra_data=json.dumps(extra_data) if extra_data else None
                )
                
                session.add(log_entry)
                await session.commit()
                return True
                
        except Exception as e:
            # Don't log this error to avoid infinite loop
            print(f"Error saving log: {e}")
            return False
    
    async def log_info(self, message: str, category: str = "system", **kwargs):
        """Convenience method for INFO logs"""
        await self.log("INFO", category, message, **kwargs)
    
    async def log_warning(self, message: str, category: str = "system", **kwargs):
        """Convenience method for WARNING logs"""
        await self.log("WARNING", category, message, **kwargs)
    
    async def log_error(self, message: str, category: str = "system", **kwargs):
        """Convenience method for ERROR logs"""
        await self.log("ERROR", category, message, **kwargs)
    
    async def log_trade(self, message: str, trade_id: str, config_id: int, **kwargs):
        """Convenience method for trade-related logs"""
        await self.log("INFO", "trade", message, config_id=config_id, trade_id=trade_id, **kwargs)
    
    # ============ Decision Operations ============
    
    async def log_decision(
        self,
        config_id: int,
        decision_type: str,
        symbol: str,
        price_a: float = None,
        price_b: float = None,
        spread: float = None,
        spread_threshold: float = None,
        action_taken: str = None,
        reason: str = None,
        position_id: str = None,
        pnl: float = None,
        extra_data: dict = None
    ) -> bool:
        """Log a bot decision to the database"""
        try:
            async with self.async_session() as session:
                from backend.models import Decision, DecisionType
                
                decision = Decision(
                    config_id=config_id,
                    decision_type=DecisionType(decision_type),
                    symbol=symbol,
                    price_a=price_a,
                    price_b=price_b,
                    spread=spread,
                    spread_threshold=spread_threshold,
                    action_taken=action_taken,
                    reason=reason,
                    position_id=position_id,
                    pnl=pnl,
                    extra_data=extra_data
                )
                
                session.add(decision)
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error logging decision: {e}")
            return False
    
    # ============ Symbol Operations ============
    
    async def load_symbols(self, config_id: int) -> List[Dict]:
        """Load enabled symbols for a config"""
        try:
            async with self.async_session() as session:
                from backend.models import SymbolConfig
                
                result = await session.execute(
                    select(SymbolConfig).where(
                        and_(
                            SymbolConfig.config_id == config_id,
                            SymbolConfig.enabled == True
                        )
                    )
                )
                symbols = result.scalars().all()
                
                return [
                    {
                        "id": s.id,
                        "symbol": s.symbol,
                        "leverage": s.leverage,
                        "position_size_usdt": s.position_size_usdt,
                        "spread_threshold": s.spread_threshold,
                        "stop_loss_percent": s.stop_loss_percent,
                        "take_profit_percent": s.take_profit_percent,
                        "max_positions": s.max_positions
                    }
                    for s in symbols
                ]
                
        except Exception as e:
            logger.error(f"Error loading symbols: {e}")
            return []


# Global database service instance
db_service: Optional[DatabaseService] = None


async def get_db_service() -> DatabaseService:
    """Get or create the global database service"""
    global db_service
    
    if db_service is None:
        db_service = DatabaseService()
        await db_service.connect()
    
    return db_service


async def close_db_service():
    """Close the global database service"""
    global db_service
    
    if db_service:
        await db_service.disconnect()
        db_service = None
