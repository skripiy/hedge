import asyncio
import ccxt.async_support as ccxt

class ExchangeManager:
    def __init__(self, exchange_id, api_key, secret):
        self.exchange_id = exchange_id
        self.exchange = getattr(ccxt, exchange_id)({
            'apiKey': api_key,
            'secret': secret,
        })

    async def fetch_ticker(self, symbol):
        return await self.exchange.fetch_ticker(symbol)

    async def create_order(self, symbol, type, side, amount, price=None):
        return await self.exchange.create_order(symbol, type, side, amount, price)
    
    async def close(self):
        await self.exchange.close()
