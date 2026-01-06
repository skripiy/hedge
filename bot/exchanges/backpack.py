"""
Backpack Exchange Connector
CEX with perpetual futures, uses ED25519 signing
API Docs: https://docs.backpack.exchange
"""
import aiohttp
import base64
import time
from typing import Optional, Dict
from datetime import datetime
import logging

from .base import BaseExchange, TickerData, OrderResult

logger = logging.getLogger(__name__)

# Backpack API endpoints
API_BASE = "https://api.backpack.exchange"
WS_BASE = "wss://ws.backpack.exchange"


class BackpackExchange(BaseExchange):
    """
    Exchange connector for Backpack Exchange (CEX).
    
    Features:
    - Low fees (0.02% maker, 0.05% taker)
    - Perpetual futures up to 10x
    - EU regulated (MiFID II)
    - ED25519 authentication
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        simulation_mode: bool = True,
        taker_fee: float = 0.05,
        maker_fee: float = 0.02,
        slippage: float = 0.02
    ):
        super().__init__(
            simulation_mode=simulation_mode,
            taker_fee=taker_fee,
            maker_fee=maker_fee,
            slippage=slippage
        )
        
        self.api_key = api_key
        self.secret = secret
        self._session: Optional[aiohttp.ClientSession] = None
        self._markets: Dict = {}
        self._signing_key = None
        
        # Initialize ED25519 signing if secret provided
        if secret and not simulation_mode:
            self._init_signing_key()
    
    def _init_signing_key(self):
        """Initialize ED25519 signing key from secret"""
        try:
            import nacl.signing
            # Decode base64 secret to get private key
            key_bytes = base64.b64decode(self.secret)
            self._signing_key = nacl.signing.SigningKey(key_bytes[:32])
            logger.info("Backpack ED25519 signing key initialized")
        except ImportError:
            logger.error("PyNaCl not installed. Run: pip install pynacl")
        except Exception as e:
            logger.error(f"Failed to init signing key: {e}")
    
    @property
    def exchange_id(self) -> str:
        return "backpack"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"}
            )
        return self._session
    
    def _sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        Sign request with ED25519.
        
        Returns headers with signature.
        """
        if not self._signing_key:
            return {}
        
        try:
            timestamp = str(int(time.time() * 1000))
            message = f"{timestamp}{method}{path}{body}"
            
            signed = self._signing_key.sign(message.encode())
            signature = base64.b64encode(signed.signature).decode()
            
            return {
                "X-API-Key": self.api_key,
                "X-Timestamp": timestamp,
                "X-Signature": signature,
            }
        except Exception as e:
            logger.error(f"Signing failed: {e}")
            return {}
    
    async def connect(self) -> bool:
        """Connect to Backpack and load markets"""
        try:
            session = await self._get_session()
            
            # Fetch available markets
            async with session.get(f"{API_BASE}/api/v1/markets") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Store markets keyed by symbol
                    self._markets = {m['symbol']: m for m in data}
                    self._connected = True
                    logger.info(f"Connected to Backpack Exchange")
                    logger.info(f"Available markets: {len(self._markets)}")
                    return True
                else:
                    logger.error(f"Failed to fetch Backpack markets: {resp.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to Backpack: {e}")
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
        Backpack uses: ETH_USD_PERP, BTC_USD_PERP
        """
        # Convert ETH/USD -> ETH_USD_PERP
        # Convert ETH/USDT -> ETH_USDT (spot)
        if "/USD" in symbol and "USDT" not in symbol:
            return symbol.replace("/", "_") + "_PERP"
        return symbol.replace("/", "_")
    
    async def fetch_ticker(self, symbol: str) -> Optional[TickerData]:
        """Fetch current ticker data"""
        try:
            session = await self._get_session()
            normalized = self.normalize_symbol(symbol)
            
            async with session.get(f"{API_BASE}/api/v1/ticker", params={"symbol": normalized}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    ticker = TickerData(
                        symbol=symbol,
                        bid=float(data.get('bestBid', 0) or 0),
                        ask=float(data.get('bestAsk', 0) or 0),
                        last=float(data.get('lastPrice', 0) or 0),
                        timestamp=datetime.utcnow()
                    )
                    
                    self._last_ticker[symbol] = ticker
                    return ticker
                else:
                    logger.error(f"Backpack ticker error: {resp.status}")
                    return self._last_ticker.get(symbol)
                    
        except Exception as e:
            logger.error(f"Error fetching Backpack ticker {symbol}: {e}")
            return self._last_ticker.get(symbol)
    
    async def fetch_balance(self) -> Dict[str, float]:
        """Fetch account balance"""
        if self.simulation_mode:
            return {"USDC": 10000.0, "USDT": 10000.0}
        
        if not self.api_key or not self.secret:
            logger.warning("API keys required for balance fetch")
            return {}
        
        try:
            session = await self._get_session()
            path = "/api/v1/capital"
            headers = self._sign_request("GET", path)
            
            async with session.get(f"{API_BASE}{path}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        item['symbol']: float(item.get('available', 0))
                        for item in data.get('balances', [])
                        if float(item.get('available', 0)) > 0
                    }
                else:
                    logger.error(f"Backpack balance error: {resp.status}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error fetching Backpack balance: {e}")
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
        
        if not self.api_key or not self.secret:
            return OrderResult(
                success=False,
                symbol=symbol,
                error="API keys required for trading"
            )
        
        try:
            session = await self._get_session()
            normalized = self.normalize_symbol(symbol)
            
            order_data = {
                "symbol": normalized,
                "side": side.upper(),
                "orderType": "Market" if order_type == "market" else "Limit",
                "quantity": str(amount),
            }
            
            if order_type == "limit" and price:
                order_data["price"] = str(price)
            
            path = "/api/v1/order"
            body = str(order_data)
            headers = self._sign_request("POST", path, body)
            
            async with session.post(f"{API_BASE}{path}", json=order_data, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return OrderResult(
                        success=True,
                        order_id=data.get('id'),
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        amount=float(data.get('quantity', amount)),
                        price=float(data.get('price', 0)),
                        timestamp=datetime.utcnow(),
                        raw_response=data
                    )
                else:
                    error = await resp.text()
                    logger.error(f"Backpack order error: {resp.status} - {error}")
                    return OrderResult(success=False, symbol=symbol, error=error)
                    
        except Exception as e:
            logger.error(f"Backpack order failed: {e}")
            return OrderResult(success=False, symbol=symbol, error=str(e))
