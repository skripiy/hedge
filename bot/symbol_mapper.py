"""
Symbol Mapper Utility
Converts symbols between different exchange formats:
- Backpack: SOL_USDC_PERP, ETH_USDC_PERP
- Ethereal: SOLUSD, ETHUSD
- CCXT (Binance/Bybit): SOL/USDT:USDT, ETH/USDT:USDT
"""

import re
from typing import Optional, Tuple

# Base currency mappings (extract base from any format)
def extract_base(symbol: str) -> str:
    """Extract base currency from any symbol format"""
    # Remove common suffixes/separators
    base = symbol.upper()
    
    # Backpack format: SOL_USDC_PERP -> SOL
    if '_USDC_PERP' in base:
        return base.replace('_USDC_PERP', '')
    if '_USD_PERP' in base:
        return base.replace('_USD_PERP', '')
    if '_USDT_PERP' in base:
        return base.replace('_USDT_PERP', '')
    
    # CCXT format: SOL/USDT:USDT -> SOL
    if '/' in base:
        return base.split('/')[0]
    
    # Ethereal format: SOLUSD -> SOL
    for quote in ['USDT', 'USDC', 'USD']:
        if base.endswith(quote):
            return base[:-len(quote)]
    
    return base


def to_backpack(symbol: str) -> str:
    """Convert any symbol to Backpack format: SOL_USDC_PERP"""
    base = extract_base(symbol)
    return f"{base}_USDC_PERP"


def to_ethereal(symbol: str) -> str:
    """Convert any symbol to Ethereal format: SOLUSD"""
    base = extract_base(symbol)
    return f"{base}USD"


def to_ccxt(symbol: str, quote: str = "USDT") -> str:
    """Convert any symbol to CCXT format: SOL/USDT:USDT"""
    base = extract_base(symbol)
    return f"{base}/{quote}:{quote}"


def to_exchange(symbol: str, exchange_id: str) -> str:
    """Convert symbol to specific exchange format"""
    exchange_id = exchange_id.lower()
    
    if exchange_id == 'backpack':
        return to_backpack(symbol)
    elif exchange_id == 'ethereal':
        return to_ethereal(symbol)
    elif exchange_id in ['binance', 'bybit', 'okx']:
        return to_ccxt(symbol)
    else:
        return symbol


def normalize_pair(symbol_a: str, symbol_b: str) -> Tuple[str, str]:
    """
    Normalize a pair of symbols to ensure they refer to the same base currency.
    Returns the base currency and whether they match.
    """
    base_a = extract_base(symbol_a)
    base_b = extract_base(symbol_b)
    return (base_a, base_a == base_b)


# Symbol mapping table for known pairs
SYMBOL_MAPPINGS = {
    # Base -> {exchange: symbol}
    'BTC': {
        'backpack': 'BTC_USDC_PERP',
        'ethereal': 'BTCUSD',
        'binance': 'BTC/USDT:USDT',
        'bybit': 'BTC/USDT:USDT',
    },
    'ETH': {
        'backpack': 'ETH_USDC_PERP',
        'ethereal': 'ETHUSD',
        'binance': 'ETH/USDT:USDT',
        'bybit': 'ETH/USDT:USDT',
    },
    'SOL': {
        'backpack': 'SOL_USDC_PERP',
        'ethereal': 'SOLUSD',
        'binance': 'SOL/USDT:USDT',
        'bybit': 'SOL/USDT:USDT',
    },
    'BNB': {
        'backpack': 'BNB_USDC_PERP',
        'ethereal': None,  # Not available on Ethereal
        'binance': 'BNB/USDT:USDT',
        'bybit': 'BNB/USDT:USDT',
    },
    'XRP': {
        'backpack': 'XRP_USDC_PERP',
        'ethereal': 'XRPUSD',
        'binance': 'XRP/USDT:USDT',
        'bybit': 'XRP/USDT:USDT',
    },
    'SUI': {
        'backpack': 'SUI_USDC_PERP',
        'ethereal': 'SUIUSD',
        'binance': 'SUI/USDT:USDT',
        'bybit': 'SUI/USDT:USDT',
    },
    'HYPE': {
        'backpack': 'HYPE_USDC_PERP',
        'ethereal': 'HYPEUSD',
        'binance': None,
        'bybit': None,
    },
    'AAVE': {
        'backpack': 'AAVE_USDC_PERP',
        'ethereal': 'AAVEUSD',
        'binance': 'AAVE/USDT:USDT',
        'bybit': 'AAVE/USDT:USDT',
    },
    'ENA': {
        'backpack': 'ENA_USDC_PERP',
        'ethereal': 'ENAUSD',
        'binance': 'ENA/USDT:USDT',
        'bybit': 'ENA/USDT:USDT',
    },
    'LIT': {
        'backpack': 'LIT_USDC_PERP',
        'ethereal': None,  # Not available
        'binance': 'LIT/USDT:USDT',
        'bybit': None,
    },
}


def get_symbol_for_exchange(base_or_symbol: str, exchange_id: str) -> Optional[str]:
    """
    Get the correct symbol format for a specific exchange.
    Input can be base currency (SOL) or any symbol format.
    Returns None if not available on that exchange.
    """
    base = extract_base(base_or_symbol)
    exchange_id = exchange_id.lower()
    
    # Check mapping table first
    if base in SYMBOL_MAPPINGS:
        mapped = SYMBOL_MAPPINGS[base].get(exchange_id)
        if mapped:
            return mapped
    
    # Fallback to conversion
    return to_exchange(base_or_symbol, exchange_id)


def get_common_symbols(exchange_a: str, exchange_b: str) -> list:
    """Get list of base currencies available on both exchanges"""
    common = []
    for base, mappings in SYMBOL_MAPPINGS.items():
        sym_a = mappings.get(exchange_a.lower())
        sym_b = mappings.get(exchange_b.lower())
        if sym_a and sym_b:
            common.append(base)
    return common
