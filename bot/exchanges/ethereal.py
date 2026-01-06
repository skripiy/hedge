"""
Ethereal Trade Exchange Connector
DEX perpetuals exchange on Ethereum
API Docs: https://docs.ethereal.trade
"""
import aiohttp
import hashlib
import json
import time
from typing import Optional, Dict
from datetime import datetime
import logging

from .base import BaseExchange, TickerData, OrderResult

logger = logging.getLogger(__name__)

# Ethereal API endpoints
MAINNET_API = "https://api.ethereal.trade"
TESTNET_API = "https://api.etherealtest.net"
MAINNET_WS = "wss://ws.ethereal.trade"


class EtherealExchange(BaseExchange):
    """
    Exchange connector for Ethereal Trade (DEX).
    
    Features:
    - Very low fees (0.03% taker)
    - On-chain perpetual futures
    - EIP712 authentication
    
    Note: Requires Ethereum private key for signing transactions.
    """
    
    def __init__(
        self,
        private_key: Optional[str] = None,
        simulation_mode: bool = True,
        taker_fee: float = 0.03,  # Ethereal's low fee
        maker_fee: float = 0.00,
        slippage: float = 0.02,
        testnet: bool = False
    ):
        super().__init__(
            simulation_mode=simulation_mode,
            taker_fee=taker_fee,
            maker_fee=maker_fee,
            slippage=slippage
        )
        
        self.private_key = private_key
        self.testnet = testnet
        self.base_url = TESTNET_API if testnet else MAINNET_API
        self._session: Optional[aiohttp.ClientSession] = None
        self._markets: Dict = {}
    
    @property
    def exchange_id(self) -> str:
        return "ethereal"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"}
            )
        return self._session
    
    async def connect(self) -> bool:
        """Connect to Ethereal and load markets"""
        try:
            session = await self._get_session()
            
            # Fetch available markets
            async with session.get(f"{self.base_url}/v1/product") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Response is array of products
                    products = data if isinstance(data, list) else data.get('products', []) if isinstance(data, dict) else []
                    self._markets = {}
                    for p in products:
                        if isinstance(p, dict):
                            ticker = p.get('ticker', p.get('symbol', p.get('id', '')))
                            if ticker:
                                self._markets[ticker] = p
                    self._connected = True
                    logger.info(f"Connected to Ethereal {'testnet' if self.testnet else 'mainnet'}")
                    logger.info(f"Available markets: {list(self._markets.keys())}")
                    return True
                else:
                    logger.error(f"Failed to fetch Ethereal markets: {resp.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to Ethereal: {e}")
            self._connected = False
            return False
    
    async def close(self):
        """Close connection"""
        if self._session and not self._session.closed:
            await self._session.close()
        self._connected = False
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format.
        Ethereal uses: ETHUSD, BTCUSD (no slash)
        """
        # Convert BTC/USDT -> BTCUSD
        normalized = symbol.replace("/USDT", "USD").replace("/", "")
        return normalized
    
    async def fetch_ticker(self, symbol: str) -> Optional[TickerData]:
        """Fetch current ticker data from Ethereal"""
        try:
            session = await self._get_session()
            normalized = self.normalize_symbol(symbol)
            
            # Try to get from cached market data first
            if normalized in self._markets:
                market = self._markets[normalized]
                mark_price = float(market.get('markPrice', 0) or market.get('lastPrice', 0) or 0)
                if mark_price > 0:
                    ticker = TickerData(
                        symbol=symbol,
                        bid=mark_price * 0.999,  # Simulate bid
                        ask=mark_price * 1.001,  # Simulate ask
                        last=mark_price,
                        timestamp=datetime.utcnow()
                    )
                    self._last_ticker[symbol] = ticker
                    return ticker
            
            # Try TradingView last-price endpoint
            async with session.get(f"https://tradingview.ethereal.trade/v1/last-price?symbol={normalized}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = float(data.get('price', 0) or data.get('last', 0) or 0)
                    if price > 0:
                        ticker = TickerData(
                            symbol=symbol,
                            bid=price * 0.999,
                            ask=price * 1.001,
                            last=price,
                            timestamp=datetime.utcnow()
                        )
                        self._last_ticker[symbol] = ticker
                        return ticker
            
            # Fallback to cached ticker
            return self._last_ticker.get(symbol)
                    
        except Exception as e:
            logger.error(f"Error fetching Ethereal ticker {symbol}: {e}")
            return self._last_ticker.get(symbol)
    
    async def fetch_balance(self) -> Dict[str, float]:
        """Fetch account balance"""
        if self.simulation_mode:
            return {"USDE": 10000.0, "USDT": 10000.0}
        
        if not self.private_key:
            logger.warning("Private key required for balance fetch")
            return {}
        
        try:
            # TODO: Implement EIP712 signed request
            # For now, return simulated balance
            return {"USDE": 10000.0}
            
        except Exception as e:
            logger.error(f"Error fetching Ethereal balance: {e}")
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
        
        if not self.private_key:
            return OrderResult(
                success=False,
                symbol=symbol,
                error="Private key required for trading"
            )
        
        try:
            # TODO: Implement EIP712 signed order placement
            # This requires:
            # 1. Create order message
            # 2. Sign with EIP712
            # 3. Submit to API
            
            logger.warning("Ethereal live trading not yet implemented")
            return await self.simulate_order(symbol, order_type, side, amount, price, leverage)
            
        except Exception as e:
            logger.error(f"Ethereal order failed: {e}")
            return OrderResult(
                success=False,
                symbol=symbol,
                error=str(e)
            )
    
    async def _sign_message(self, message: dict) -> str:
        """
        Sign message with EIP712.
        TODO: Implement proper EIP712 signing
        """
        # Placeholder - needs eth-account library
        return ""
