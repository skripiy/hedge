"""
Trading Strategy for Delta-Neutral Hedging
Handles entry/exit logic and position management
"""
import asyncio
import uuid
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from bot.exchange import ExchangeManager, OrderResult, fetch_spread

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass
class HedgePosition:
    """Represents a delta-neutral hedge position across two exchanges"""
    position_id: str
    symbol: str
    status: PositionStatus = PositionStatus.PENDING
    
    # Exchange info
    exchange_a: str = ""  # Long side
    exchange_b: str = ""  # Short side
    
    # Entry data
    entry_price_a: float = 0.0
    entry_price_b: float = 0.0
    entry_amount: float = 0.0  # Amount in base currency
    entry_amount_usdt: float = 0.0
    leverage: int = 1
    
    # Current data
    current_price_a: float = 0.0
    current_price_b: float = 0.0
    
    # Order IDs
    order_id_a: Optional[str] = None
    order_id_b: Optional[str] = None
    
    # PnL tracking
    pnl_a: float = 0.0  # Long PnL
    pnl_b: float = 0.0  # Short PnL
    fees_paid: float = 0.0
    
    # Timestamps
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    close_reason: Optional[str] = None
    
    # Exit data
    exit_price_a: float = 0.0
    exit_price_b: float = 0.0
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized PnL"""
        if self.status != PositionStatus.OPEN:
            return 0.0
        
        # Long PnL: (current - entry) * amount
        pnl_long = (self.current_price_a - self.entry_price_a) * self.entry_amount
        
        # Short PnL: (entry - current) * amount
        pnl_short = (self.entry_price_b - self.current_price_b) * self.entry_amount
        
        return pnl_long + pnl_short - self.fees_paid
    
    @property
    def realized_pnl(self) -> float:
        """Calculate realized PnL (after close)"""
        if self.status != PositionStatus.CLOSED:
            return 0.0
        return self.pnl_a + self.pnl_b - self.fees_paid
    
    def update_prices(self, price_a: float, price_b: float):
        """Update current prices and recalculate PnL"""
        self.current_price_a = price_a
        self.current_price_b = price_b
        
        if self.status == PositionStatus.OPEN:
            self.pnl_a = (price_a - self.entry_price_a) * self.entry_amount
            self.pnl_b = (self.entry_price_b - price_b) * self.entry_amount


class Strategy:
    """
    Delta-neutral hedging strategy.
    Opens simultaneous long/short positions on two exchanges.
    """
    
    def __init__(
        self,
        exchange_a: ExchangeManager,
        exchange_b: ExchangeManager,
        symbol: str = "BTC/USDT",
        position_size_usdt: float = 100.0,
        leverage: int = 1,
        spread_threshold: float = 0.5,  # Min spread % for entry
        stop_loss_percent: float = 2.0,
        take_profit_percent: float = 5.0,
        order_type: str = "market"
    ):
        self.ex_a = exchange_a
        self.ex_b = exchange_b
        self.symbol = symbol
        self.position_size_usdt = position_size_usdt
        self.leverage = leverage
        self.spread_threshold = spread_threshold
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.order_type = order_type
        
        # Active positions
        self.positions: Dict[str, HedgePosition] = {}
        
        # Callbacks
        self.on_position_opened = None
        self.on_position_closed = None
        self.on_position_updated = None
    
    async def check_entry_opportunity(self) -> Optional[Tuple[float, float, float]]:
        """
        Check if there's an entry opportunity based on spread.
        Returns (spread_percent, price_a, price_b) or None
        """
        spread, ticker_a, ticker_b = await fetch_spread(
            self.ex_a, self.ex_b, self.symbol
        )
        
        if spread is None or not ticker_a or not ticker_b:
            return None
        
        logger.debug(
            f"Spread: {spread:.4f}% | {self.ex_a.exchange_id}: {ticker_a.mid:.2f} | "
            f"{self.ex_b.exchange_id}: {ticker_b.mid:.2f}"
        )
        
        # Check if spread exceeds threshold
        if abs(spread) >= self.spread_threshold:
            return spread, ticker_a.mid, ticker_b.mid
        
        return None
    
    async def open_position(
        self,
        price_hint_a: Optional[float] = None,
        price_hint_b: Optional[float] = None
    ) -> Optional[HedgePosition]:
        """
        Open a delta-neutral position.
        Long on exchange A, Short on exchange B.
        Uses asyncio.gather for parallel execution.
        """
        position_id = str(uuid.uuid4())[:8]
        
        # Get current prices if not provided
        if not price_hint_a or not price_hint_b:
            ticker_a = await self.ex_a.fetch_ticker(self.symbol)
            ticker_b = await self.ex_b.fetch_ticker(self.symbol)
            if not ticker_a or not ticker_b:
                logger.error("Failed to fetch prices for position entry")
                return None
            price_hint_a = ticker_a.mid
            price_hint_b = ticker_b.mid
        
        # Calculate position size in base currency
        avg_price = (price_hint_a + price_hint_b) / 2
        amount = (self.position_size_usdt * self.leverage) / avg_price
        
        logger.info(
            f"Opening hedge position {position_id}: "
            f"{amount:.6f} {self.symbol} @ ~{avg_price:.2f}"
        )
        
        # Create pending position
        position = HedgePosition(
            position_id=position_id,
            symbol=self.symbol,
            status=PositionStatus.PENDING,
            exchange_a=self.ex_a.exchange_id,
            exchange_b=self.ex_b.exchange_id,
            entry_amount=amount,
            entry_amount_usdt=self.position_size_usdt,
            leverage=self.leverage
        )
        
        # Execute orders in parallel using asyncio.gather
        try:
            order_a, order_b = await asyncio.gather(
                self.ex_a.create_order(
                    symbol=self.symbol,
                    order_type=self.order_type,
                    side='buy',  # Long on A
                    amount=amount,
                    price=price_hint_a if self.order_type == 'limit' else None,
                    leverage=self.leverage
                ),
                self.ex_b.create_order(
                    symbol=self.symbol,
                    order_type=self.order_type,
                    side='sell',  # Short on B
                    amount=amount,
                    price=price_hint_b if self.order_type == 'limit' else None,
                    leverage=self.leverage
                ),
                return_exceptions=True
            )
            
            # Handle exceptions from gather
            if isinstance(order_a, Exception):
                order_a = OrderResult(success=False, error=str(order_a))
            if isinstance(order_b, Exception):
                order_b = OrderResult(success=False, error=str(order_b))
            
        except Exception as e:
            logger.error(f"Error executing parallel orders: {e}")
            position.status = PositionStatus.FAILED
            return position
        
        # Check results and handle rollback if needed
        if order_a.success and order_b.success:
            # Both orders succeeded
            position.status = PositionStatus.OPEN
            position.order_id_a = order_a.order_id
            position.order_id_b = order_b.order_id
            position.entry_price_a = order_a.price
            position.entry_price_b = order_b.price
            position.current_price_a = order_a.price
            position.current_price_b = order_b.price
            position.fees_paid = order_a.fee + order_b.fee
            position.open_time = datetime.utcnow()
            
            self.positions[position_id] = position
            
            logger.info(
                f"Position {position_id} opened successfully. "
                f"Entry A: {order_a.price:.2f}, Entry B: {order_b.price:.2f}, "
                f"Fees: {position.fees_paid:.4f}"
            )
            
            if self.on_position_opened:
                await self.on_position_opened(position)
            
            return position
        
        else:
            # One or both orders failed - ROLLBACK
            logger.warning(f"Position entry failed. Initiating rollback...")
            await self._rollback(order_a, order_b, amount)
            position.status = PositionStatus.FAILED
            return position
    
    async def _rollback(
        self,
        order_a: OrderResult,
        order_b: OrderResult,
        amount: float
    ):
        """
        Rollback mechanism: If one order succeeded and the other failed,
        immediately close the successful position to avoid directional exposure.
        """
        if order_a.success and not order_b.success:
            # Order A succeeded, B failed - close position on A
            logger.warning(
                f"Order B failed ({order_b.error}). Rolling back order A..."
            )
            rollback_result = await self.ex_a.close_position(
                self.symbol, 'long', amount
            )
            if rollback_result.success:
                logger.info("Rollback successful: Position A closed")
            else:
                logger.error(f"CRITICAL: Rollback failed! {rollback_result.error}")
        
        elif order_b.success and not order_a.success:
            # Order B succeeded, A failed - close position on B
            logger.warning(
                f"Order A failed ({order_a.error}). Rolling back order B..."
            )
            rollback_result = await self.ex_b.close_position(
                self.symbol, 'short', amount
            )
            if rollback_result.success:
                logger.info("Rollback successful: Position B closed")
            else:
                logger.error(f"CRITICAL: Rollback failed! {rollback_result.error}")
        
        else:
            # Both failed
            logger.error(
                f"Both orders failed. A: {order_a.error}, B: {order_b.error}"
            )
    
    async def close_position(
        self,
        position_id: str,
        reason: str = "manual"
    ) -> bool:
        """Close a specific position"""
        position = self.positions.get(position_id)
        if not position or position.status != PositionStatus.OPEN:
            logger.warning(f"Position {position_id} not found or not open")
            return False
        
        position.status = PositionStatus.CLOSING
        
        logger.info(f"Closing position {position_id}, reason: {reason}")
        
        # Close both legs in parallel
        try:
            close_a, close_b = await asyncio.gather(
                self.ex_a.close_position(self.symbol, 'long', position.entry_amount),
                self.ex_b.close_position(self.symbol, 'short', position.entry_amount),
                return_exceptions=True
            )
            
            if isinstance(close_a, Exception):
                close_a = OrderResult(success=False, error=str(close_a))
            if isinstance(close_b, Exception):
                close_b = OrderResult(success=False, error=str(close_b))
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
        
        # Calculate final PnL
        if close_a.success:
            position.exit_price_a = close_a.price
            position.pnl_a = (close_a.price - position.entry_price_a) * position.entry_amount
            position.fees_paid += close_a.fee
        
        if close_b.success:
            position.exit_price_b = close_b.price
            position.pnl_b = (position.entry_price_b - close_b.price) * position.entry_amount
            position.fees_paid += close_b.fee
        
        position.status = PositionStatus.CLOSED
        position.close_time = datetime.utcnow()
        position.close_reason = reason
        
        logger.info(
            f"Position {position_id} closed. "
            f"PnL A: {position.pnl_a:.4f}, PnL B: {position.pnl_b:.4f}, "
            f"Net: {position.realized_pnl:.4f}"
        )
        
        if self.on_position_closed:
            await self.on_position_closed(position)
        
        return True
    
    async def close_all_positions(self, reason: str = "panic") -> int:
        """Close all open positions (Panic Button)"""
        closed_count = 0
        open_positions = [
            p for p in self.positions.values()
            if p.status == PositionStatus.OPEN
        ]
        
        for position in open_positions:
            if await self.close_position(position.position_id, reason):
                closed_count += 1
        
        return closed_count
    
    async def update_positions(self):
        """Update all open positions with current prices"""
        for position in self.positions.values():
            if position.status != PositionStatus.OPEN:
                continue
            
            ticker_a = await self.ex_a.fetch_ticker(self.symbol)
            ticker_b = await self.ex_b.fetch_ticker(self.symbol)
            
            if ticker_a and ticker_b:
                position.update_prices(ticker_a.mid, ticker_b.mid)
                
                if self.on_position_updated:
                    await self.on_position_updated(position)
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized PnL across all open positions"""
        return sum(
            p.unrealized_pnl for p in self.positions.values()
            if p.status == PositionStatus.OPEN
        )
    
    def get_open_positions(self) -> List[HedgePosition]:
        """Get list of open positions"""
        return [
            p for p in self.positions.values()
            if p.status == PositionStatus.OPEN
        ]
