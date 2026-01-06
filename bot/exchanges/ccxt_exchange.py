"""
CCXT Exchange Connector
Wrapper for exchanges supported by CCXT library (Binance, Bybit, OKX, etc.)
"""
import ccxt.async_support as ccxt
from typing import Optional, Dict
from datetime import datetime
import logging

from .base import BaseExchange, TickerData, OrderResult

logger = logging.getLogger(__name__)


class CCXTExchange(BaseExchange):
    """
    Exchange connector using CCXT library.
    Supports: Binance, Bybit, OKX, and other CCXT-compatible exchanges.
    """
    
    def __init__(
        self,
        exchange_id: str,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        simulation_mode: bool = True,
        taker_fee: float = 0.05,
        maker_fee: float = 0.02,
        slippage: float = 0.02,
        sandbox: bool = False
    ):
        super().__init__(
            simulation_mode=simulation_mode,
            taker_fee=taker_fee,
            maker_fee=maker_fee,
            slippage=slippage
        )
        
        self._exchange_id = exchange_id.lower()
        
        # Get CCXT exchange class
        exchange_class = getattr(ccxt, self._exchange_id, None)
        if not exchange_class:
            raise ValueError(f"Exchange '{exchange_id}' not supported by CCXT")
        
        # Configure exchange
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
    
    @property
    def exchange_id(self) -> str:
        return self._exchange_id
    
    async def connect(self) -> bool:
        """Connect to exchange and load markets"""
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
            return {"USDT": 10000.0}
        
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
    
    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        leverage: int = 1
    ) -> OrderResult:
        """Create order (simulated or real)"""
        
        if self.simulation_mode:
            return await self.simulate_order(symbol, order_type, side, amount, price, leverage)
        
        # Real order execution
        try:
            # Set leverage if supported
            if hasattr(self.exchange, 'set_leverage') and leverage > 1:
                try:
                    await self.exchange.set_leverage(leverage, symbol)
                except Exception as e:
                    logger.warning(f"Could not set leverage: {e}")
            
            # Create order
            if order_type == 'market':
                order = await self.exchange.create_market_order(symbol, side, amount)
            else:
                order = await self.exchange.create_limit_order(symbol, side, amount, price)
            
            return OrderResult(
                success=True,
                order_id=order.get('id'),
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=order.get('amount', amount),
                price=order.get('price', order.get('average', 0)),
                cost=order.get('cost', 0),
                fee=order.get('fee', {}).get('cost', 0),
                timestamp=datetime.utcnow(),
                raw_response=order
            )
            
        except Exception as e:
            logger.error(f"Order failed on {self.exchange_id}: {e}")
            return OrderResult(
                success=False,
                symbol=symbol,
                side=side,
                order_type=order_type,
                error=str(e)
            )
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order"""
        if self.simulation_mode:
            return True
        
        try:
            await self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"Cancel order failed on {self.exchange_id}: {e}")
            return False
    
    async def fetch_order(self, order_id: str, symbol: str) -> Optional[Dict]:
        """Fetch order status"""
        if self.simulation_mode:
            return None
        
        try:
            return await self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            logger.error(f"Fetch order failed on {self.exchange_id}: {e}")
            return None
