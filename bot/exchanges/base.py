"""
Base Exchange Class
Abstract interface that all exchange connectors must implement
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class TickerData:
    """Ticker/price data from exchange"""
    symbol: str
    bid: float  # Best bid price
    ask: float  # Best ask price
    last: float  # Last trade price
    timestamp: datetime
    
    @property
    def mid(self) -> float:
        """Mid-market price"""
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        """Bid-ask spread in %"""
        if self.mid == 0:
            return 0
        return ((self.ask - self.bid) / self.mid) * 100


@dataclass
class OrderResult:
    """Result of an order execution (real or simulated)"""
    success: bool
    order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""  # buy/sell
    order_type: str = ""  # market/limit
    amount: float = 0.0
    price: float = 0.0
    cost: float = 0.0  # Total cost in quote currency
    fee: float = 0.0  # Fee paid
    slippage: float = 0.0  # Slippage applied
    timestamp: Optional[datetime] = None
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


class BaseExchange(ABC):
    """
    Abstract base class for exchange connectors.
    All exchange implementations must inherit from this class.
    """
    
    def __init__(
        self,
        simulation_mode: bool = True,
        taker_fee: float = 0.05,  # 0.05%
        maker_fee: float = 0.02,  # 0.02%
        slippage: float = 0.02,   # 0.02%
    ):
        self.simulation_mode = simulation_mode
        self.taker_fee = taker_fee / 100  # Convert to decimal
        self.maker_fee = maker_fee / 100
        self.slippage = slippage / 100
        self._connected = False
        self._last_ticker: Dict[str, TickerData] = {}
    
    @property
    @abstractmethod
    def exchange_id(self) -> str:
        """Return exchange identifier (e.g., 'binance', 'ethereal')"""
        pass
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to exchange.
        Returns True if successful.
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close connection to exchange"""
        pass
    
    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Optional[TickerData]:
        """
        Fetch current ticker/price data for a symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT', 'ETHUSD')
            
        Returns:
            TickerData or None if error
        """
        pass
    
    @abstractmethod
    async def fetch_balance(self) -> Dict[str, float]:
        """
        Fetch account balances.
        
        Returns:
            Dict mapping currency to available balance
        """
        pass
    
    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        order_type: str,  # 'market' or 'limit'
        side: str,  # 'buy' or 'sell'
        amount: float,  # Amount in base currency
        price: Optional[float] = None,  # Required for limit orders
        leverage: int = 1
    ) -> OrderResult:
        """
        Create an order (real or simulated).
        
        Args:
            symbol: Trading pair
            order_type: 'market' or 'limit'
            side: 'buy' or 'sell'
            amount: Amount in base currency
            price: Limit price (required for limit orders)
            leverage: Leverage multiplier
            
        Returns:
            OrderResult with execution details
        """
        pass
    
    async def simulate_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        leverage: int = 1
    ) -> OrderResult:
        """
        Simulate an order execution with realistic fees and slippage.
        Can be overridden but provides default implementation.
        """
        try:
            ticker = await self.fetch_ticker(symbol)
            if not ticker:
                return OrderResult(
                    success=False,
                    symbol=symbol,
                    error="Failed to fetch ticker"
                )
            
            # Determine execution price with slippage
            if order_type == 'market':
                if side == 'buy':
                    exec_price = ticker.ask * (1 + self.slippage)
                else:
                    exec_price = ticker.bid * (1 - self.slippage)
                fee_rate = self.taker_fee
                slippage_applied = abs(exec_price - ticker.mid) / ticker.mid if ticker.mid else 0
            else:
                exec_price = price or ticker.mid
                fee_rate = self.maker_fee
                slippage_applied = 0.0
            
            cost = amount * exec_price
            fee = cost * fee_rate
            
            return OrderResult(
                success=True,
                order_id=f"SIM-{self.exchange_id}-{datetime.utcnow().timestamp()}",
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=amount,
                price=exec_price,
                cost=cost,
                fee=fee,
                slippage=slippage_applied,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Simulation error on {self.exchange_id}: {e}")
            return OrderResult(success=False, symbol=symbol, error=str(e))
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format to exchange-specific format.
        Override in subclass if needed.
        """
        return symbol
