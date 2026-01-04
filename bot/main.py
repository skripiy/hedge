import asyncio
from bot.exchange import ExchangeManager
from bot.strategy import Strategy
import os

async def main():
    print("Starting HedgeBot...")
    # Initialize exchanges
    # This is just a skeleton. In real app, we load from config/DB.
    
    # ex_a = ExchangeManager('binance', 'key', 'secret')
    # ex_b = ExchangeManager('bybit', 'key', 'secret')
    
    # strategy = Strategy(ex_a, ex_b)
    
    while True:
        # await strategy.execute()
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
