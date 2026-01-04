"""
Risk Manager for HedgeBot
Handles stop-loss, take-profit, daily limits, and emergency actions
"""
import asyncio
from typing import Optional, Callable, Awaitable, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

from bot.strategy import Strategy, HedgePosition, PositionStatus

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Risk management limits configuration"""
    # Per-position limits
    stop_loss_percent: float = 2.0  # Close if position PnL < -X%
    take_profit_percent: float = 5.0  # Close if position PnL > +X%
    
    # Global limits (USDT)
    global_stop_loss: float = 500.0  # Close all if total PnL < -X USDT
    global_take_profit: float = 1000.0  # Close all if total PnL > +X USDT
    max_daily_loss: float = 500.0  # Stop trading if daily loss > X USDT
    
    # Position limits
    max_open_positions: int = 5
    max_position_size_usdt: float = 1000.0
    
    # Time limits
    max_position_duration_hours: float = 24.0  # Auto-close after X hours


@dataclass
class RiskState:
    """Current risk state tracking"""
    total_pnl_today: float = 0.0
    day_start: datetime = field(default_factory=lambda: datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0))
    trading_halted: bool = False
    halt_reason: Optional[str] = None
    positions_closed_today: int = 0
    stop_losses_triggered: int = 0
    take_profits_triggered: int = 0


class RiskManager:
    """
    Risk Manager for monitoring and enforcing risk limits.
    Runs as a background task checking positions periodically.
    """
    
    def __init__(
        self,
        strategy: Strategy,
        limits: Optional[RiskLimits] = None,
        check_interval: float = 1.0  # Check every N seconds
    ):
        self.strategy = strategy
        self.limits = limits or RiskLimits()
        self.check_interval = check_interval
        self.state = RiskState()
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Event callbacks
        self.on_stop_loss: Optional[Callable[[HedgePosition], Awaitable[None]]] = None
        self.on_take_profit: Optional[Callable[[HedgePosition], Awaitable[None]]] = None
        self.on_trading_halted: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_risk_alert: Optional[Callable[[str, str], Awaitable[None]]] = None
    
    async def start(self):
        """Start the risk monitoring loop"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("Risk Manager started")
    
    async def stop(self):
        """Stop the risk monitoring loop"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Risk Manager stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                await self._check_all_risks()
            except Exception as e:
                logger.error(f"Error in risk monitoring: {e}")
            
            await asyncio.sleep(self.check_interval)
    
    async def _check_all_risks(self):
        """Run all risk checks"""
        # Reset daily stats if new day
        self._check_day_reset()
        
        # Skip if trading is halted
        if self.state.trading_halted:
            return
        
        # Update position prices first
        await self.strategy.update_positions()
        
        # Check each open position
        for position in self.strategy.get_open_positions():
            await self._check_position_risks(position)
        
        # Check global limits
        await self._check_global_risks()
    
    def _check_day_reset(self):
        """Reset daily stats at midnight UTC"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if today_start > self.state.day_start:
            logger.info("New trading day - resetting daily stats")
            self.state = RiskState(day_start=today_start)
    
    async def _check_position_risks(self, position: HedgePosition):
        """Check risk limits for a single position"""
        if position.status != PositionStatus.OPEN:
            return
        
        pnl = position.unrealized_pnl
        pnl_percent = (pnl / position.entry_amount_usdt) * 100 if position.entry_amount_usdt > 0 else 0
        
        # Check stop-loss
        if pnl_percent <= -self.limits.stop_loss_percent:
            logger.warning(
                f"STOP-LOSS triggered for {position.position_id}: "
                f"PnL {pnl_percent:.2f}% (limit: -{self.limits.stop_loss_percent}%)"
            )
            await self._close_with_reason(position, "stop_loss")
            self.state.stop_losses_triggered += 1
            
            if self.on_stop_loss:
                await self.on_stop_loss(position)
            return
        
        # Check take-profit
        if pnl_percent >= self.limits.take_profit_percent:
            logger.info(
                f"TAKE-PROFIT triggered for {position.position_id}: "
                f"PnL {pnl_percent:.2f}% (limit: +{self.limits.take_profit_percent}%)"
            )
            await self._close_with_reason(position, "take_profit")
            self.state.take_profits_triggered += 1
            
            if self.on_take_profit:
                await self.on_take_profit(position)
            return
        
        # Check max duration
        if position.open_time:
            duration = (datetime.utcnow() - position.open_time).total_seconds() / 3600
            if duration >= self.limits.max_position_duration_hours:
                logger.info(
                    f"Position {position.position_id} exceeded max duration "
                    f"({duration:.1f}h > {self.limits.max_position_duration_hours}h)"
                )
                await self._close_with_reason(position, "max_duration")
    
    async def _check_global_risks(self):
        """Check global risk limits across all positions"""
        total_pnl = self.strategy.get_total_unrealized_pnl()
        
        # Check global stop-loss
        if total_pnl <= -self.limits.global_stop_loss:
            await self._halt_trading(
                f"Global stop-loss triggered: Total PnL {total_pnl:.2f} USDT",
                close_all=True
            )
            return
        
        # Check global take-profit
        if total_pnl >= self.limits.global_take_profit:
            await self._halt_trading(
                f"Global take-profit reached: Total PnL {total_pnl:.2f} USDT",
                close_all=True
            )
            return
        
        # Check daily loss limit
        if self.state.total_pnl_today <= -self.limits.max_daily_loss:
            await self._halt_trading(
                f"Daily loss limit reached: {self.state.total_pnl_today:.2f} USDT",
                close_all=False  # Keep positions, just stop new entries
            )
    
    async def _close_with_reason(self, position: HedgePosition, reason: str):
        """Close a position and track the PnL"""
        pnl_before = position.unrealized_pnl
        
        success = await self.strategy.close_position(position.position_id, reason)
        
        if success:
            self.state.positions_closed_today += 1
            self.state.total_pnl_today += pnl_before
    
    async def _halt_trading(self, reason: str, close_all: bool = False):
        """Halt trading due to risk limit breach"""
        logger.warning(f"TRADING HALTED: {reason}")
        
        self.state.trading_halted = True
        self.state.halt_reason = reason
        
        if close_all:
            closed = await self.strategy.close_all_positions("risk_limit")
            logger.info(f"Closed {closed} positions due to risk limit")
        
        if self.on_trading_halted:
            await self.on_trading_halted(reason)
    
    def resume_trading(self):
        """Resume trading after halt"""
        if not self.state.trading_halted:
            return
        
        logger.info("Trading resumed")
        self.state.trading_halted = False
        self.state.halt_reason = None
    
    def can_open_position(self, size_usdt: float) -> tuple[bool, Optional[str]]:
        """
        Check if a new position can be opened.
        Returns (allowed, reason_if_not_allowed)
        """
        if self.state.trading_halted:
            return False, f"Trading halted: {self.state.halt_reason}"
        
        # Check position count limit
        open_count = len(self.strategy.get_open_positions())
        if open_count >= self.limits.max_open_positions:
            return False, f"Max open positions reached ({open_count}/{self.limits.max_open_positions})"
        
        # Check position size
        if size_usdt > self.limits.max_position_size_usdt:
            return False, f"Position size too large ({size_usdt} > {self.limits.max_position_size_usdt})"
        
        # Check daily loss
        if self.state.total_pnl_today <= -self.limits.max_daily_loss * 0.8:
            return False, f"Approaching daily loss limit ({self.state.total_pnl_today:.2f})"
        
        return True, None
    
    def get_status(self) -> Dict:
        """Get current risk manager status"""
        return {
            "trading_halted": self.state.trading_halted,
            "halt_reason": self.state.halt_reason,
            "total_pnl_today": self.state.total_pnl_today,
            "positions_closed_today": self.state.positions_closed_today,
            "stop_losses_triggered": self.state.stop_losses_triggered,
            "take_profits_triggered": self.state.take_profits_triggered,
            "open_positions": len(self.strategy.get_open_positions()),
            "unrealized_pnl": self.strategy.get_total_unrealized_pnl(),
            "limits": {
                "stop_loss_percent": self.limits.stop_loss_percent,
                "take_profit_percent": self.limits.take_profit_percent,
                "global_stop_loss": self.limits.global_stop_loss,
                "max_daily_loss": self.limits.max_daily_loss,
                "max_open_positions": self.limits.max_open_positions
            }
        }


async def emergency_close_all(strategy: Strategy) -> int:
    """
    Emergency function to close all positions immediately.
    Can be called from API (Panic Button).
    """
    logger.critical("EMERGENCY: Closing all positions!")
    return await strategy.close_all_positions("panic")
