"""
Volume Farming Strategy with Break-Even Logic
Focuses on maximizing trading volume while ensuring no losses on fees.
"""
import asyncio
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

from bot.exchange import ExchangeManager, TickerData

logger = logging.getLogger(__name__)


@dataclass
class VolumeStrategyConfig:
    """Configuration for Volume Farming strategy"""
    min_hold_time_minutes: int = 60
    max_hold_time_minutes: int = 480
    close_only_if_profitable: bool = True
    min_entry_spread_percent: float = 0.30
    emergency_stop_loss_percent: float = 2.0
    target_profit_percent: float = 0.15
    taker_fee_percent: float = 0.05
    maker_fee_percent: float = 0.02
    slippage_percent: float = 0.02
    use_maker_orders: bool = False
    
    @property
    def break_even_spread(self) -> float:
        """Calculate minimum spread to cover all fees"""
        fee = self.maker_fee_percent if self.use_maker_orders else self.taker_fee_percent
        # 4 fees: open long, open short, close long, close short
        # Plus slippage on each side
        total = (fee * 4) + (self.slippage_percent * 2)
        return total
    
    @property
    def min_profit_for_close(self) -> float:
        """Minimum PnL percent to allow closing"""
        return self.break_even_spread


class CloseDecision(Enum):
    HOLD = "hold"
    PROFITABLE_CLOSE = "profitable_close"
    EARLY_PROFIT = "early_profit"
    EMERGENCY_STOP_LOSS = "emergency_stop_loss"
    MAX_HOLD_TIME = "max_hold_time_forced"


class VolumeStrategy:
    """
    Volume Farming strategy with Break-Even logic.
    
    Priorities:
    1. Maximize trading volume
    2. Keep PnL divergence high (far from zero on each exchange)
    3. Hold positions for minimum time (1h+)
    4. Never close at a loss (except emergency SL)
    """
    
    def __init__(
        self,
        exchange_a: ExchangeManager,
        exchange_b: ExchangeManager,
        config: VolumeStrategyConfig = None
    ):
        self.ex_a = exchange_a
        self.ex_b = exchange_b
        self.config = config or VolumeStrategyConfig()
        
        # Active positions tracking
        self.positions: Dict[str, dict] = {}
        
        # Callbacks
        self.on_position_opened = None
        self.on_position_closed = None
    
    def calculate_break_even_spread(self) -> float:
        """Get minimum spread required for profitable entry"""
        return self.config.break_even_spread
    
    async def should_enter(
        self, 
        symbol: str,
        current_spread: float
    ) -> Tuple[bool, str]:
        """
        Determine if we should enter a position.
        
        Returns:
            (should_enter, reason)
        """
        min_spread = self.config.min_entry_spread_percent
        break_even = self.calculate_break_even_spread()
        
        # Use the larger of configured min or break-even
        effective_min = max(min_spread, break_even)
        
        if abs(current_spread) >= effective_min:
            return True, f"Spread {current_spread:.4f}% >= {effective_min:.4f}% (covers fees)"
        
        return False, f"Spread {current_spread:.4f}% < {effective_min:.4f}% (would not cover fees)"
    
    def should_close(
        self,
        position: dict,
        current_pnl_percent: float,
        elapsed_time: timedelta
    ) -> Tuple[CloseDecision, str]:
        """
        Determine if we should close a position.
        
        Key rule: Only close when profitable (covers fees) OR emergency.
        
        Returns:
            (decision, reason)
        """
        min_hold = timedelta(minutes=self.config.min_hold_time_minutes)
        max_hold = timedelta(minutes=self.config.max_hold_time_minutes)
        min_profit = self.config.min_profit_for_close
        target_profit = self.config.target_profit_percent
        emergency_sl = -self.config.emergency_stop_loss_percent
        
        # 1. Emergency stop-loss - always close immediately
        if current_pnl_percent <= emergency_sl:
            return CloseDecision.EMERGENCY_STOP_LOSS, f"PnL {current_pnl_percent:.4f}% <= {emergency_sl}%"
        
        # 2. Force close at max hold time
        if elapsed_time >= max_hold:
            return CloseDecision.MAX_HOLD_TIME, f"Max hold time {self.config.max_hold_time_minutes}m exceeded"
        
        # 3. WAIT for min_hold_time before considering any exit (except emergency SL)
        if elapsed_time < min_hold:
            remaining = min_hold - elapsed_time
            mins_left = int(remaining.total_seconds() / 60)
            return CloseDecision.HOLD, f"Hold time: {mins_left}m remaining until min hold"
        
        # 4. After min_hold_time reached - check if profitable
        if self.config.close_only_if_profitable:
            if current_pnl_percent >= min_profit:
                return CloseDecision.PROFITABLE_CLOSE, f"Min hold reached, profit {current_pnl_percent:.4f}% >= {min_profit}%"
            else:
                return CloseDecision.HOLD, f"Min hold reached but PnL {current_pnl_percent:.4f}% < {min_profit}% - waiting"
        else:
            return CloseDecision.PROFITABLE_CLOSE, f"Hold time {elapsed_time} >= {min_hold}, closing"
        
        # 5. Keep holding (fallback)
        return CloseDecision.HOLD, f"Holding - waiting for conditions"
    
    def calculate_volume_generated(
        self,
        position_size_usdt: float,
        leverage: int
    ) -> float:
        """
        Calculate volume generated by a trade.
        Volume = position_size × 2 (open + close) × leverage
        """
        return position_size_usdt * 2 * leverage
    
    def calculate_pnl_divergence(
        self,
        pnl_a: float,
        pnl_b: float
    ) -> float:
        """
        Calculate PnL divergence between exchanges.
        Higher divergence is better for volume farming.
        """
        return abs(pnl_a) + abs(pnl_b)
    
    async def get_current_spread(
        self,
        symbol: str
    ) -> Optional[Tuple[float, float, float]]:
        """
        Get current spread between exchanges.
        
        Returns:
            (spread_percent, price_a, price_b) or None
        """
        try:
            ticker_a = await self.ex_a.fetch_ticker(symbol)
            ticker_b = await self.ex_b.fetch_ticker(symbol)
            
            if not ticker_a or not ticker_b:
                return None
            
            price_a = ticker_a.last
            price_b = ticker_b.last
            
            if not price_a or not price_b:
                return None
            
            spread = ((price_a - price_b) / price_b) * 100
            return spread, price_a, price_b
            
        except Exception as e:
            logger.error(f"Error fetching spread for {symbol}: {e}")
            return None
