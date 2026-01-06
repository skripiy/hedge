"""
Exchange Connectors Package
Provides unified interface for multiple exchanges
"""
from .base import BaseExchange, TickerData, OrderResult
from .ccxt_exchange import CCXTExchange

# Exchange registry
SUPPORTED_EXCHANGES = {
    # CCXT-based exchanges
    'binance': 'ccxt',
    'bybit': 'ccxt',
    'okx': 'ccxt',
    # Custom connectors
    'ethereal': 'ethereal',
    'backpack': 'backpack',
}


def create_exchange(
    exchange_id: str,
    api_key: str = None,
    secret: str = None,
    private_key: str = None,  # For Ethereal
    simulation_mode: bool = True,
    **kwargs
) -> BaseExchange:
    """
    Factory function to create exchange connector.
    
    Args:
        exchange_id: Exchange identifier (binance, bybit, ethereal, backpack)
        api_key: API key (for CEX)
        secret: API secret (for CEX)
        private_key: Ethereum private key (for Ethereal)
        simulation_mode: Whether to use paper trading
        
    Returns:
        BaseExchange instance
    """
    exchange_type = SUPPORTED_EXCHANGES.get(exchange_id.lower())
    
    if not exchange_type:
        raise ValueError(f"Exchange '{exchange_id}' not supported. Available: {list(SUPPORTED_EXCHANGES.keys())}")
    
    if exchange_type == 'ccxt':
        return CCXTExchange(
            exchange_id=exchange_id,
            api_key=api_key,
            secret=secret,
            simulation_mode=simulation_mode,
            **kwargs
        )
    elif exchange_type == 'ethereal':
        from .ethereal import EtherealExchange
        return EtherealExchange(
            private_key=private_key,
            simulation_mode=simulation_mode,
            **kwargs
        )
    elif exchange_type == 'backpack':
        from .backpack import BackpackExchange
        return BackpackExchange(
            api_key=api_key,
            secret=secret,
            simulation_mode=simulation_mode,
            **kwargs
        )
    
    raise ValueError(f"Unknown exchange type: {exchange_type}")
