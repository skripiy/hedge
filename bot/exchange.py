"""
Exchange Manager - CCXT wrapper for HedgeBot
Handles both simulation and live trading
"""
import asyncio
import ccxt.async_support as ccxt
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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
        return ((self.ask - self.bid) / self.mid) * 100


class ExchangeManager:
    """
    Wrapper over CCXT for exchange operations.
    Supports both simulation (paper trading) and live trading.
    """
    
    def __init__(
        self,
        exchange_id: str,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        simulation_mode: bool = True,
        taker_fee: float = 0.1,  # 0.1%
        maker_fee: float = 0.05,  # 0.05%
        slippage: float = 0.05,  # 0.05%
        sandbox: bool = False
    ):
        self.exchange_id = exchange_id
        self.simulation_mode = simulation_mode
        self.taker_fee = taker_fee / 100  # Convert to decimal
        self.maker_fee = maker_fee / 100
        self.slippage = slippage / 100
        
        # Initialize exchange
        exchange_class = getattr(ccxt, exchange_id, None)
        if not exchange_class:
            raise ValueError(f"Exchange '{exchange_id}' not supported")
        
        config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Use futures by default
            }
        }
        
        if api_key and secret:
            config['apiKey'] = api_key
            config['secret'] = secret
        
        self.exchange = exchange_class(config)
        
        if sandbox:
            self.exchange.set_sandbox_mode(True)
        
        self._connected = False
        self._last_ticker: Dict[str, TickerData] = {}
    
    async def connect(self) -> bool:
        """Test connection to exchange"""
        try:
            await self.exchange.load_markets()
            self._connected = True
            logger.info(f"Connected to {self.exchange_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.exchange_id}: {e}")
            self._connected = False
            return False
    
    async def close(self):
        """Close exchange connection"""
        try:
            await self.exchange.close()
            self._connected = False
        except Exception as e:
            logger.error(f"Error closing {self.exchange_id}: {e}")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def fetch_ticker(self, symbol: str) -> Optional[TickerData]:
        """Fetch current ticker/price data"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            
            data = TickerData(
                symbol=symbol,
                bid=ticker.get('bid', 0) or ticker.get('last', 0),
                ask=ticker.get('ask', 0) or ticker.get('last', 0),
                last=ticker.get('last', 0),
                timestamp=datetime.utcnow()
            )
            
            self._last_ticker[symbol] = data
            return data
            
        except Exception as e:
            logger.error(f"Error fetching ticker {symbol} from {self.exchange_id}: {e}")
            return self._last_ticker.get(symbol)
    
    async def fetch_balance(self) -> Dict[str, float]:
        """Fetch account balance"""
        if self.simulation_mode:
            return {"USDT": 10000.0}  # Simulated balance
        
        try:
            balance = await self.exchange.fetch_balance()
            return {
                currency: data['free']
                for currency, data in balance.items()
                if isinstance(data, dict) and data.get('free', 0) > 0
            }
        except Exception as e:
            logger.error(f"Error fetching balance from {self.exchange_id}: {e}")
            return {}
    
    async def simulate_order(
        self,
        symbol: str,
        order_type: str,  # 'market' or 'limit'
        side: str,  # 'buy' or 'sell'
        amount: float,  # Amount in base currency
        price: Optional[float] = None,  # Required for limit orders
        leverage: int = 1
    ) -> OrderResult:
        """
        Simulate an order execution.
        Accounts for fees and slippage for realistic results.
        """
        try:
            # Get current price
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
                    # Buying at ask + slippage
                    exec_price = ticker.ask * (1 + self.slippage)
                else:
                    # Selling at bid - slippage
                    exec_price = ticker.bid * (1 - self.slippage)
                fee_rate = self.taker_fee
                slippage_applied = abs(exec_price - ticker.mid) / ticker.mid
            else:
                # Limit order - use specified price, no slippage
                exec_price = price or ticker.mid
                fee_rate = self.maker_fee
                slippage_applied = 0.0
            
            # Calculate cost and fee
            cost = amount * exec_price
            fee = cost * fee_rate
            
            # Generate simulated order ID
            order_id = f"SIM-{self.exchange_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            
            logger.info(
                f"[SIM] {self.exchange_id} {side.upper()} {amount} {symbol} "
                f"@ {exec_price:.2f} (fee: {fee:.4f})"
            )
            
            return OrderResult(
                success=True,
                order_id=order_id,
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
            logger.error(f"Simulation error: {e}")
            return OrderResult(
                success=False,
                symbol=symbol,
                side=side,
                error=str(e)
            )
    
    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        leverage: int = 1,
        params: Optional[Dict] = None
    ) -> OrderResult:
        """
        Create a real or simulated order depending on mode.
        """
        if self.simulation_mode:
            return await self.simulate_order(
                symbol, order_type, side, amount, price, leverage
            )
        
        # Live trading
        try:
            # Set leverage if supported
            try:
                await self.exchange.set_leverage(leverage, symbol)
            except Exception:
                pass  # Not all exchanges support this
            
            # Place order
            order = await self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=params or {}
            )
            
            # Calculate fee
            fee = 0.0
            if order.get('fee'):
                fee = order['fee'].get('cost', 0) or 0
            else:
                cost = order.get('cost', 0) or (amount * (order.get('price', 0) or 0))
                fee = cost * self.taker_fee
            
            logger.info(
                f"[LIVE] {self.exchange_id} {side.upper()} {amount} {symbol} "
                f"@ {order.get('price', 'market')} (order_id: {order['id']})"
            )
            
            return OrderResult(
                success=True,
                order_id=order['id'],
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=order.get('filled', amount),
                price=order.get('average', order.get('price', 0)) or 0,
                cost=order.get('cost', 0) or 0,
                fee=fee,
                slippage=0.0,
                timestamp=datetime.utcnow(),
                raw_response=order
            )
            
        except Exception as e:
            logger.error(f"Order error on {self.exchange_id}: {e}")
            return OrderResult(
                success=False,
                symbol=symbol,
                side=side,
                error=str(e)
            )
    
    async def close_position(
        self,
        symbol: str,
        side: str,  # 'long' or 'short'
        amount: float
    ) -> OrderResult:
        """Close a position with market order"""
        # To close long, we sell. To close short, we buy.
        close_side = 'sell' if side == 'long' else 'buy'
        
        return await self.create_order(
            symbol=symbol,
            order_type='market',
            side=close_side,
            amount=amount
        )
    
    async def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for a symbol"""
        if self.simulation_mode:
            return None
        
        try:
            positions = await self.exchange.fetch_positions([symbol])
            for pos in positions:
                if pos['symbol'] == symbol and pos['contracts'] > 0:
                    return pos
            return None
        except Exception as e:
            logger.error(f"Error fetching position: {e}")
            return None


async def fetch_spread(
    exchange_a: ExchangeManager,
    exchange_b: ExchangeManager,
    symbol: str
) -> Tuple[Optional[float], Optional[TickerData], Optional[TickerData]]:
    """
    Fetch price spread between two exchanges.
    Returns (spread_percent, ticker_a, ticker_b)
    """
    ticker_a, ticker_b = await asyncio.gather(
        exchange_a.fetch_ticker(symbol),
        exchange_b.fetch_ticker(symbol)
    )
    
    if not ticker_a or not ticker_b:
        return None, ticker_a, ticker_b
    
    # Calculate spread as percentage difference
    spread = ((ticker_a.mid - ticker_b.mid) / ticker_b.mid) * 100
    
    return spread, ticker_a, ticker_b
