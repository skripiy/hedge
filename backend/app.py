"""
HedgeBot API Server
FastAPI application with all endpoints for bot control and monitoring
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from backend.database import get_db, init_db, close_db
from backend.models import (
    BotConfig, Trade, Log, SymbolConfig, Decision, PriceCache,
    TradingMode, BotStatus, TradeStatus, DecisionType
)
from backend.schemas import (
    ConfigCreate, ConfigUpdate, ConfigResponse,
    TradeResponse, TradeCloseRequest,
    BotStatusResponse, PositionSummary,
    LogCreate, LogResponse,
    StartBotRequest, StopBotRequest, PanicCloseRequest, ActionResponse
)

# Create FastAPI app
app = FastAPI(
    title="HedgeBot API",
    description="API for Delta-Neutral Trading Bot",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bot start time for uptime calculation
BOT_START_TIME: Optional[datetime] = None


# ============ Lifecycle Events ============

@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    await init_db()
    
    # Auto-migrate: add new Volume Farming columns
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS strategy_mode VARCHAR(30) DEFAULT 'hedge'",
        "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS min_hold_time_minutes INTEGER DEFAULT 60",
        "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS max_hold_time_minutes INTEGER DEFAULT 480",
        "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS close_only_if_profitable BOOLEAN DEFAULT TRUE",
        "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS min_entry_spread_percent FLOAT DEFAULT 0.30",
        "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS target_daily_volume FLOAT DEFAULT 100000.0",
        "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS max_concurrent_positions INTEGER DEFAULT 5",
        "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS use_maker_orders BOOLEAN DEFAULT FALSE",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS volume_generated FLOAT DEFAULT 0.0",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS hold_duration_seconds INTEGER",
    ]
    try:
        async for db in get_db():
            for sql in migrations:
                await db.execute(text(sql))
            await db.commit()
            break
    except Exception as e:
        print(f"Migration note: {e}")
    
    # Create default config if not exists
    async for db in get_db():
        result = await db.execute(select(BotConfig).where(BotConfig.id == 1))
        if not result.scalar_one_or_none():
            default_config = BotConfig(name="Default Strategy")
            db.add(default_config)
            await db.commit()
        break


@app.on_event("shutdown")
async def shutdown():
    """Close database connections on shutdown"""
    await close_db()


# ============ Health Check ============

@app.get("/", tags=["Health"])
async def root():
    """API health check"""
    return {"status": "ok", "message": "HedgeBot API is running"}


@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check including database"""
    try:
        await db.execute(select(1))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============ Bot Control ============

@app.post("/start", response_model=ActionResponse, tags=["Control"])
async def start_bot(request: StartBotRequest, db: AsyncSession = Depends(get_db)):
    """Start the trading bot"""
    global BOT_START_TIME
    
    # Get config
    result = await db.execute(select(BotConfig).where(BotConfig.id == request.config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if config.status == BotStatus.RUNNING:
        return ActionResponse(success=False, message="Bot is already running")
    
    # Check API keys for live mode
    if config.mode == TradingMode.LIVE:
        if not config.api_key_a or not config.api_secret_a:
            raise HTTPException(status_code=400, detail="API keys for Exchange A required for live trading")
        if not config.api_key_b or not config.api_secret_b:
            raise HTTPException(status_code=400, detail="API keys for Exchange B required for live trading")
    
    # Update status
    config.status = BotStatus.RUNNING
    await db.commit()
    
    BOT_START_TIME = datetime.utcnow()
    
    # Log action
    log = Log(level="INFO", category="system", message=f"Bot started in {config.mode.value} mode", config_id=config.id)
    db.add(log)
    await db.commit()
    
    return ActionResponse(
        success=True, 
        message=f"Bot started in {config.mode.value} mode",
        data={"config_id": config.id, "mode": config.mode.value}
    )


@app.post("/stop", response_model=ActionResponse, tags=["Control"])
async def stop_bot(request: StopBotRequest, db: AsyncSession = Depends(get_db)):
    """Stop the trading bot"""
    global BOT_START_TIME
    
    result = await db.execute(select(BotConfig).where(BotConfig.id == request.config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if config.status == BotStatus.STOPPED:
        return ActionResponse(success=False, message="Bot is already stopped")
    
    # Close positions if requested
    if request.close_positions:
        # Get open trades
        trades_result = await db.execute(
            select(Trade).where(
                and_(Trade.config_id == config.id, Trade.status == TradeStatus.OPEN)
            )
        )
        open_trades = trades_result.scalars().all()
        
        for trade in open_trades:
            trade.status = TradeStatus.CLOSED
            trade.close_time = datetime.utcnow()
            trade.close_reason = "bot_stop"
        
        await db.commit()
    
    config.status = BotStatus.STOPPED
    await db.commit()
    
    BOT_START_TIME = None
    
    log = Log(level="INFO", category="system", message="Bot stopped", config_id=config.id)
    db.add(log)
    await db.commit()
    
    return ActionResponse(success=True, message="Bot stopped")


@app.post("/panic", response_model=ActionResponse, tags=["Control"])
async def panic_close(request: PanicCloseRequest, db: AsyncSession = Depends(get_db)):
    """Emergency close all positions (Panic Button)"""
    result = await db.execute(select(BotConfig).where(BotConfig.id == request.config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Get all open trades
    trades_result = await db.execute(
        select(Trade).where(
            and_(Trade.config_id == config.id, Trade.status == TradeStatus.OPEN)
        )
    )
    open_trades = trades_result.scalars().all()
    
    closed_count = 0
    for trade in open_trades:
        trade.status = TradeStatus.CLOSED
        trade.close_time = datetime.utcnow()
        trade.close_reason = "panic"
        # In real implementation, send market close orders here
        closed_count += 1
    
    await db.commit()
    
    log = Log(
        level="WARNING", 
        category="risk", 
        message=f"PANIC: Closed {closed_count} positions", 
        config_id=config.id
    )
    db.add(log)
    await db.commit()
    
    return ActionResponse(
        success=True, 
        message=f"Emergency closed {closed_count} positions",
        data={"closed_count": closed_count}
    )


# ============ Status ============

@app.get("/status", response_model=BotStatusResponse, tags=["Status"])
async def get_status(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get current bot status"""
    result = await db.execute(select(BotConfig).where(BotConfig.id == config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Count open positions
    positions_result = await db.execute(
        select(func.count(Trade.id)).where(
            and_(Trade.config_id == config_id, Trade.status == TradeStatus.OPEN)
        )
    )
    open_positions_count = positions_result.scalar() or 0
    
    # Calculate unrealized PnL
    pnl_result = await db.execute(
        select(func.sum(Trade.unrealized_pnl)).where(
            and_(Trade.config_id == config_id, Trade.status == TradeStatus.OPEN)
        )
    )
    unrealized_pnl = pnl_result.scalar() or 0.0
    
    # Calculate today's realized PnL
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_pnl_result = await db.execute(
        select(func.sum(Trade.pnl_net)).where(
            and_(
                Trade.config_id == config_id, 
                Trade.status == TradeStatus.CLOSED,
                Trade.close_time >= today_start
            )
        )
    )
    total_pnl_today = today_pnl_result.scalar() or 0.0
    
    # Calculate uptime
    uptime = None
    if BOT_START_TIME and config.status == BotStatus.RUNNING:
        uptime = int((datetime.utcnow() - BOT_START_TIME).total_seconds())
    
    return BotStatusResponse(
        status=config.status,
        mode=config.mode,
        current_balance=config.current_balance,
        unrealized_pnl=unrealized_pnl,
        total_pnl_today=total_pnl_today,
        open_positions_count=open_positions_count,
        uptime_seconds=uptime,
        last_activity=None,
        # Per-exchange info (split balance 50/50 for simulation)
        exchange_a=config.exchange_a or "binance",
        exchange_b=config.exchange_b or "bybit",
        balance_a=config.current_balance / 2,
        balance_b=config.current_balance / 2,
        # Connection status
        exchange_a_connected=config.status == BotStatus.RUNNING,
        exchange_b_connected=config.status == BotStatus.RUNNING,
        database_connected=True
    )


# ============ Positions ============

@app.get("/positions", response_model=List[PositionSummary], tags=["Positions"])
async def get_positions(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get all open positions (fast - no live price fetching)"""
    result = await db.execute(
        select(Trade).where(
            and_(Trade.config_id == config_id, Trade.status == TradeStatus.OPEN)
        ).order_by(Trade.open_time.desc())
    )
    trades = result.scalars().all()
    
    if not trades:
        return []
    
    positions = []
    for trade in trades:
        # Use stored prices (updated by bot periodically)
        current_price_a = trade.current_price_a or trade.entry_price_a
        current_price_b = trade.current_price_b or trade.entry_price_b
        
        # Calculate PnL from stored values
        pnl_a = (current_price_a - trade.entry_price_a) * trade.entry_amount if trade.entry_amount else 0
        pnl_b = (trade.entry_price_b - current_price_b) * trade.entry_amount if trade.entry_amount else 0
        total_pnl = pnl_a + pnl_b - (trade.fees_paid or 0)
        
        positions.append(PositionSummary(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            exchange_a=trade.exchange_a,
            exchange_b=trade.exchange_b,
            entry_price_a=trade.entry_price_a,
            entry_price_b=trade.entry_price_b,
            current_price_a=current_price_a,
            current_price_b=current_price_b,
            amount_usdt=trade.entry_amount_usdt,
            pnl_a=round(pnl_a, 4),
            pnl_b=round(pnl_b, 4),
            total_pnl=round(total_pnl, 4),
            open_time=trade.open_time
        ))
    
    return positions


@app.post("/positions/{trade_id}/close", response_model=ActionResponse, tags=["Positions"])
async def close_position(trade_id: str, request: TradeCloseRequest, db: AsyncSession = Depends(get_db)):
    """Close a specific position"""
    result = await db.execute(select(Trade).where(Trade.trade_id == trade_id))
    trade = result.scalar_one_or_none()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade.status != TradeStatus.OPEN:
        return ActionResponse(success=False, message="Trade is not open")
    
    # Close the trade
    trade.status = TradeStatus.CLOSED
    trade.close_time = datetime.utcnow()
    trade.close_reason = request.reason
    
    # TODO: In real implementation, calculate final PnL based on exit prices
    trade.exit_price_a = trade.current_price_a or trade.entry_price_a
    trade.exit_price_b = trade.current_price_b or trade.entry_price_b
    trade.pnl_net = trade.unrealized_pnl
    
    await db.commit()
    
    log = Log(
        level="INFO", 
        category="trade", 
        message=f"Position closed: {trade_id}, reason: {request.reason}, PnL: {trade.pnl_net}",
        trade_id=trade_id,
        config_id=trade.config_id
    )
    db.add(log)
    await db.commit()
    
    return ActionResponse(success=True, message=f"Position closed with PnL: {trade.pnl_net}")


# ============ Trades History ============

@app.get("/trades", response_model=List[TradeResponse], tags=["Trades"])
async def get_trades(
    config_id: int = 1,
    status: Optional[TradeStatus] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get trade history"""
    query = select(Trade).where(Trade.config_id == config_id)
    
    if status:
        query = query.where(Trade.status == status)
    
    query = query.order_by(Trade.open_time.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    trades = result.scalars().all()
    
    return trades


@app.get("/trades/{trade_id}", response_model=TradeResponse, tags=["Trades"])
async def get_trade(trade_id: str, db: AsyncSession = Depends(get_db)):
    """Get specific trade details"""
    result = await db.execute(select(Trade).where(Trade.trade_id == trade_id))
    trade = result.scalar_one_or_none()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    return trade


# ============ Configuration ============

@app.get("/config", response_model=ConfigResponse, tags=["Config"])
async def get_config(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get bot configuration"""
    result = await db.execute(select(BotConfig).where(BotConfig.id == config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Convert to response with hidden API keys - use getattr for optional fields
    response = ConfigResponse(
        id=config.id,
        name=config.name,
        mode=config.mode,
        status=config.status,
        virtual_balance=config.virtual_balance,
        current_balance=config.current_balance,
        exchange_a=config.exchange_a,
        exchange_b=config.exchange_b,
        max_daily_loss=config.max_daily_loss,
        taker_fee=config.taker_fee,
        maker_fee=config.maker_fee,
        slippage=config.slippage,
        # Volume Farming fields
        strategy_mode=getattr(config, 'strategy_mode', 'volume_break_even'),
        min_hold_time_minutes=getattr(config, 'min_hold_time_minutes', 60),
        max_hold_time_minutes=getattr(config, 'max_hold_time_minutes', 480),
        use_maker_orders=getattr(config, 'use_maker_orders', False),
        created_at=config.created_at,
        updated_at=config.updated_at,
        has_api_keys_a=bool(getattr(config, 'api_key_a', None) and getattr(config, 'api_secret_a', None)),
        has_api_keys_b=bool(getattr(config, 'api_key_b', None) and getattr(config, 'api_secret_b', None))
    )
    
    return response


@app.put("/config", response_model=ConfigResponse, tags=["Config"])
async def update_config(config_update: ConfigUpdate, config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Update bot configuration"""
    result = await db.execute(select(BotConfig).where(BotConfig.id == config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Don't allow config changes while running (except stop)
    if config.status == BotStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot update config while bot is running. Stop the bot first.")
    
    # Update fields
    update_data = config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    
    await db.commit()
    await db.refresh(config)
    
    log = Log(level="INFO", category="system", message="Configuration updated", config_id=config.id)
    db.add(log)
    await db.commit()
    
    return await get_config(config_id, db)


@app.post("/config", response_model=ConfigResponse, tags=["Config"])
async def create_config(config_create: ConfigCreate, db: AsyncSession = Depends(get_db)):
    """Create new bot configuration"""
    new_config = BotConfig(**config_create.model_dump())
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)
    
    return await get_config(new_config.id, db)


# ============ Logs ============

@app.get("/logs", response_model=List[LogResponse], tags=["Logs"])
async def get_logs(
    config_id: Optional[int] = None,
    level: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get system logs"""
    query = select(Log)
    
    if config_id:
        query = query.where(Log.config_id == config_id)
    if level:
        query = query.where(Log.level == level)
    if category:
        query = query.where(Log.category == category)
    
    query = query.order_by(Log.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return logs


@app.post("/logs", response_model=LogResponse, tags=["Logs"])
async def create_log(log_create: LogCreate, db: AsyncSession = Depends(get_db)):
    """Create a log entry"""
    new_log = Log(**log_create.model_dump())
    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)
    
    return new_log


# ============ Analytics ============

@app.get("/analytics/equity", tags=["Analytics"])
async def get_equity_curve(
    config_id: int = 1,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get equity curve data for charts"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(Trade).where(
            and_(
                Trade.config_id == config_id,
                Trade.status == TradeStatus.CLOSED,
                Trade.close_time >= start_date
            )
        ).order_by(Trade.close_time)
    )
    trades = result.scalars().all()
    
    # Get initial balance
    config_result = await db.execute(select(BotConfig).where(BotConfig.id == config_id))
    config = config_result.scalar_one_or_none()
    initial_balance = config.virtual_balance if config else 10000.0
    
    # Build equity curve
    equity_curve = []
    running_balance = initial_balance
    
    for trade in trades:
        running_balance += trade.pnl_net
        equity_curve.append({
            "timestamp": trade.close_time.isoformat() if trade.close_time else None,
            "balance": running_balance,
            "pnl": trade.pnl_net,
            "trade_id": trade.trade_id
        })
    
    return {
        "initial_balance": initial_balance,
        "current_balance": running_balance,
        "total_pnl": running_balance - initial_balance,
        "total_trades": len(trades),
        "data": equity_curve
    }


@app.get("/analytics/summary", tags=["Analytics"])
async def get_analytics_summary(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get trading summary statistics including volume metrics"""
    # Total trades
    total_result = await db.execute(
        select(func.count(Trade.id)).where(Trade.config_id == config_id)
    )
    total_trades = total_result.scalar() or 0
    
    # Winning trades
    win_result = await db.execute(
        select(func.count(Trade.id)).where(
            and_(Trade.config_id == config_id, Trade.pnl_net > 0)
        )
    )
    winning_trades = win_result.scalar() or 0
    
    # Total PnL
    pnl_result = await db.execute(
        select(func.sum(Trade.pnl_net)).where(Trade.config_id == config_id)
    )
    total_pnl = pnl_result.scalar() or 0.0
    
    # Fees paid
    fees_result = await db.execute(
        select(func.sum(Trade.fees_paid)).where(Trade.config_id == config_id)
    )
    total_fees = fees_result.scalar() or 0.0
    
    # Volume generated (new)
    volume_result = await db.execute(
        select(func.sum(Trade.volume_generated)).where(Trade.config_id == config_id)
    )
    total_volume = volume_result.scalar() or 0.0
    
    # Average hold time in seconds (new)
    hold_result = await db.execute(
        select(func.avg(Trade.hold_duration_seconds)).where(
            and_(Trade.config_id == config_id, Trade.hold_duration_seconds.isnot(None))
        )
    )
    avg_hold_seconds = hold_result.scalar() or 0
    
    # Today's volume (include open trades)
    from datetime import date
    today = date.today()
    today_vol_result = await db.execute(
        select(func.sum(Trade.volume_generated)).where(
            and_(
                Trade.config_id == config_id,
                func.date(Trade.open_time) == today
            )
        )
    )
    today_volume = today_vol_result.scalar() or 0.0
    
    # Open positions count
    open_result = await db.execute(
        select(func.count(Trade.id)).where(
            and_(Trade.config_id == config_id, Trade.status == TradeStatus.OPEN)
        )
    )
    open_positions = open_result.scalar() or 0
    
    # Unrealized PnL for open positions (sum of volume_generated for open trades as proxy)
    # Real unrealized PnL requires live prices, so we estimate from volume
    unrealized_result = await db.execute(
        select(func.sum(Trade.unrealized_pnl)).where(
            and_(Trade.config_id == config_id, Trade.status == TradeStatus.OPEN)
        )
    )
    unrealized_pnl = unrealized_result.scalar() or 0.0
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Format hold time
    avg_hold_minutes = round(avg_hold_seconds / 60, 1) if avg_hold_seconds else 0
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": total_trades - winning_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "total_fees": round(total_fees, 2),
        "net_pnl": round(total_pnl - total_fees, 2),
        # Volume Farming metrics
        "total_volume": round(total_volume, 2),
        "today_volume": round(today_volume, 2),
        "avg_hold_minutes": avg_hold_minutes,
        # Open positions
        "open_positions": open_positions,
        "unrealized_pnl": round(unrealized_pnl, 2)
    }


# ============ Symbol Configuration ============

@app.get("/available-symbols", tags=["Symbols"])
async def get_available_symbols(
    exchange: str = "binance",
    quote_currency: str = "USDT"
):
    """
    Fetch available trading pairs from an exchange.
    Supports: binance, bybit, okx, ethereal, backpack
    """
    import aiohttp
    
    symbols = []
    
    try:
        if exchange.lower() in ['binance', 'bybit', 'okx']:
            # Use CCXT for CEX
            import ccxt.async_support as ccxt
            exchange_class = getattr(ccxt, exchange.lower())
            ex = exchange_class({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
            
            try:
                markets = await ex.load_markets()
                symbols = [
                    symbol for symbol in markets.keys()
                    if quote_currency in symbol and ':' in symbol  # Futures pairs
                ]
                symbols = sorted(symbols)[:50]  # Limit to 50
            finally:
                await ex.close()
                
        elif exchange.lower() == 'ethereal':
            # Ethereal Trade - fetch from API
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.ethereal.trade/v1/products") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        symbols = [p.get('symbol', '') for p in data.get('products', [])]
                    else:
                        symbols = ['ETHUSD', 'BTCUSD', 'SOLUSD']  # Fallback
                        
        elif exchange.lower() == 'backpack':
            # Backpack Exchange - fetch from API
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.backpack.exchange/api/v1/markets") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        symbols = [
                            m.get('symbol', '') for m in data 
                            if 'PERP' in m.get('symbol', '')  # Filter perpetuals
                        ]
                    else:
                        symbols = ['ETH_USD_PERP', 'BTC_USD_PERP', 'SOL_USD_PERP']  # Fallback
        else:
            return {"error": f"Exchange '{exchange}' not supported", "symbols": []}
            
    except Exception as e:
        logger.error(f"Error fetching symbols from {exchange}: {e}")
        return {"error": str(e), "symbols": []}
    
    return {
        "exchange": exchange,
        "count": len(symbols),
        "symbols": symbols
    }


@app.get("/markets", tags=["Symbols"])
async def get_markets(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """
    Get common markets available on both configured exchanges.
    Returns intersection of perpetual futures pairs.
    """
    import aiohttp
    
    # Get exchange config
    result = await db.execute(select(BotConfig).where(BotConfig.id == config_id))
    config = result.scalar_one_or_none()
    
    if not config:
        logger.error("Config not found")
        return {"markets": [], "error": "Config not found"}
    
    exchange_a = config.exchange_a or "binance"
    exchange_b = config.exchange_b or "bybit"
    
    logger.info(f"Fetching markets for: {exchange_a} + {exchange_b}")
    
    async def fetch_symbols(exchange: str) -> list:
        """Fetch symbols from an exchange"""
        try:
            if exchange.lower() in ['binance', 'bybit', 'okx']:
                import ccxt.async_support as ccxt
                exchange_class = getattr(ccxt, exchange.lower())
                ex = exchange_class({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
                try:
                    markets = await ex.load_markets()
                    symbols = [
                        {
                            'symbol': sym,
                            'base': markets[sym].get('base', ''),
                            'quote': markets[sym].get('quote', ''),
                            'type': 'future',
                            'last': float(markets[sym].get('info', {}).get('lastPrice', 0) or 0),
                            'volume_24h': float(markets[sym].get('info', {}).get('volume', 0) or 0),
                        }
                        for sym in markets.keys()
                        if ':' in sym  # Futures have ':' in symbol
                    ]
                    logger.info(f"{exchange}: found {len(symbols)} futures pairs")
                    return symbols
                finally:
                    await ex.close()
                    
            elif exchange.lower() == 'ethereal':
                logger.info(f"Fetching from Ethereal API...")
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://api.ethereal.trade/v1/products", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        logger.info(f"Ethereal response: {resp.status}")
                        if resp.status == 200:
                            data = await resp.json()
                            products = data.get('products', []) if isinstance(data, dict) else data
                            symbols = [
                                {
                                    'symbol': p.get('symbol', '') if isinstance(p, dict) else str(p),
                                    'base': (p.get('symbol', '') if isinstance(p, dict) else str(p)).replace('USD', ''),
                                    'quote': 'USD',
                                    'type': 'perp',
                                    'last': 0,
                                    'volume_24h': 0,
                                }
                                for p in products
                            ]
                            logger.info(f"Ethereal: found {len(symbols)} pairs")
                            return symbols
                        else:
                            text = await resp.text()
                            logger.error(f"Ethereal error: {resp.status} - {text[:200]}")
                return []
                
            elif exchange.lower() == 'backpack':
                logger.info(f"Fetching from Backpack API...")
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://api.backpack.exchange/api/v1/markets", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        logger.info(f"Backpack response: {resp.status}")
                        if resp.status == 200:
                            data = await resp.json()
                            symbols = [
                                {
                                    'symbol': m.get('symbol', ''),
                                    'base': m.get('baseSymbol', m.get('symbol', '').split('_')[0]),
                                    'quote': m.get('quoteSymbol', 'USD'),
                                    'type': 'perp' if 'PERP' in m.get('symbol', '') else 'spot',
                                    'last': float(m.get('lastPrice', 0) or 0),
                                    'volume_24h': float(m.get('volume', 0) or 0),
                                }
                                for m in data
                            ]
                            # Filter to perps only
                            perps = [s for s in symbols if s['type'] == 'perp']
                            logger.info(f"Backpack: found {len(perps)} perp pairs (total {len(symbols)})")
                            return perps if perps else symbols[:50]  # Return spot if no perps
                        else:
                            text = await resp.text()
                            logger.error(f"Backpack error: {resp.status} - {text[:200]}")
                return []
            else:
                logger.warning(f"Unknown exchange: {exchange}")
                return []
        except Exception as e:
            logger.error(f"Error fetching from {exchange}: {e}")
            return []
    
    # Fetch from both exchanges
    symbols_a = await fetch_symbols(exchange_a)
    symbols_b = await fetch_symbols(exchange_b)
    
    logger.info(f"Exchange A ({exchange_a}): {len(symbols_a)} symbols")
    logger.info(f"Exchange B ({exchange_b}): {len(symbols_b)} symbols")
    
    # If one exchange has no results, just show the other
    if not symbols_a and symbols_b:
        return {
            "exchange_a": exchange_a,
            "exchange_b": exchange_b,
            "total_a": 0,
            "total_b": len(symbols_b),
            "count": len(symbols_b),
            "markets": symbols_b[:100]
        }
    elif symbols_a and not symbols_b:
        return {
            "exchange_a": exchange_a,
            "exchange_b": exchange_b,
            "total_a": len(symbols_a),
            "total_b": 0,
            "count": len(symbols_a),
            "markets": symbols_a[:100]
        }
    
    # Find common base currencies
    bases_a = {s['base'] for s in symbols_a}
    bases_b = {s['base'] for s in symbols_b}
    common_bases = bases_a & bases_b
    
    logger.info(f"Common bases: {len(common_bases)}")
    
    # Return symbols from exchange A that are also available on B
    common_markets = [s for s in symbols_a if s['base'] in common_bases]
    
    # If no common, return all from exchange A
    if not common_markets:
        common_markets = symbols_a
    
    # Sort by volume
    common_markets.sort(key=lambda x: x.get('volume_24h', 0), reverse=True)
    
    return {
        "exchange_a": exchange_a,
        "exchange_b": exchange_b,
        "total_a": len(symbols_a),
        "total_b": len(symbols_b),
        "count": len(common_markets),
        "markets": common_markets[:100]
    }

@app.get("/symbols", tags=["Symbols"])
async def get_symbols(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get all configured symbols"""
    result = await db.execute(
        select(SymbolConfig).where(SymbolConfig.config_id == config_id)
    )
    symbols = result.scalars().all()
    
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "enabled": s.enabled,
            "leverage": s.leverage,
            "position_size_usdt": s.position_size_usdt,
            "spread_threshold": s.spread_threshold,
            "stop_loss_percent": s.stop_loss_percent,
            "take_profit_percent": s.take_profit_percent,
            "max_positions": s.max_positions
        }
        for s in symbols
    ]


@app.post("/symbols", tags=["Symbols"])
async def add_symbol(
    symbol: str,
    config_id: int = 1,
    enabled: bool = True,
    leverage: int = 1,
    position_size_usdt: float = 100.0,
    spread_threshold: float = 0.5,
    stop_loss_percent: float = 2.0,
    take_profit_percent: float = 5.0,
    db: AsyncSession = Depends(get_db)
):
    """Add a new symbol to monitor"""
    # Check if symbol already exists
    result = await db.execute(
        select(SymbolConfig).where(
            and_(SymbolConfig.config_id == config_id, SymbolConfig.symbol == symbol)
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} already configured")
    
    new_symbol = SymbolConfig(
        config_id=config_id,
        symbol=symbol,
        enabled=enabled,
        leverage=leverage,
        position_size_usdt=position_size_usdt,
        spread_threshold=spread_threshold,
        stop_loss_percent=stop_loss_percent,
        take_profit_percent=take_profit_percent
    )
    
    db.add(new_symbol)
    await db.commit()
    await db.refresh(new_symbol)
    
    return {"success": True, "id": new_symbol.id, "symbol": symbol}


@app.put("/symbols/{symbol_id}", tags=["Symbols"])
async def update_symbol(
    symbol_id: int,
    enabled: Optional[bool] = None,
    leverage: Optional[int] = None,
    position_size_usdt: Optional[float] = None,
    spread_threshold: Optional[float] = None,
    stop_loss_percent: Optional[float] = None,
    take_profit_percent: Optional[float] = None,
    db: AsyncSession = Depends(get_db)
):
    """Update symbol configuration"""
    result = await db.execute(select(SymbolConfig).where(SymbolConfig.id == symbol_id))
    symbol_config = result.scalar_one_or_none()
    
    if not symbol_config:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    if enabled is not None:
        symbol_config.enabled = enabled
    if leverage is not None:
        symbol_config.leverage = leverage
    if position_size_usdt is not None:
        symbol_config.position_size_usdt = position_size_usdt
    if spread_threshold is not None:
        symbol_config.spread_threshold = spread_threshold
    if stop_loss_percent is not None:
        symbol_config.stop_loss_percent = stop_loss_percent
    if take_profit_percent is not None:
        symbol_config.take_profit_percent = take_profit_percent
    
    await db.commit()
    return {"success": True, "message": "Symbol updated"}


@app.delete("/symbols/{symbol_id}", tags=["Symbols"])
async def delete_symbol(symbol_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a symbol configuration"""
    result = await db.execute(select(SymbolConfig).where(SymbolConfig.id == symbol_id))
    symbol_config = result.scalar_one_or_none()
    
    if not symbol_config:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    await db.delete(symbol_config)
    await db.commit()
    return {"success": True, "message": "Symbol deleted"}


# ============ Available Markets (from exchanges) ============

@app.get("/markets", tags=["Markets"])
async def get_available_markets(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get trading pairs available on BOTH configured exchanges"""
    import ccxt.async_support as ccxt
    
    # Get config to know which exchanges to compare
    config_result = await db.execute(select(BotConfig).where(BotConfig.id == config_id))
    config = config_result.scalar_one_or_none()
    
    if not config:
        return {"error": "Config not found", "markets": []}
    
    exchange_a = config.exchange_a
    exchange_b = config.exchange_b
    
    try:
        # Initialize both exchanges
        ex_a_class = getattr(ccxt, exchange_a.lower())
        ex_b_class = getattr(ccxt, exchange_b.lower())
        
        ex_a = ex_a_class({'enableRateLimit': True})
        ex_b = ex_b_class({'enableRateLimit': True})
        
        # Load markets from both
        await ex_a.load_markets()
        await ex_b.load_markets()
        
        # Get USDT symbols from each exchange
        symbols_a = set()
        symbols_b = set()
        
        for symbol, market in ex_a.markets.items():
            if market.get('quote') == 'USDT' and market.get('active', True):
                symbols_a.add(symbol)
        
        for symbol, market in ex_b.markets.items():
            if market.get('quote') == 'USDT' and market.get('active', True):
                symbols_b.add(symbol)
        
        # Get intersection - symbols on BOTH exchanges
        common_symbols = symbols_a & symbols_b
        
        # Fetch all tickers for price/volume info
        tickers_a = {}
        tickers_b = {}
        try:
            # fetch_tickers() without params gets all tickers
            all_tickers_a = await ex_a.fetch_tickers()
            tickers_a = {s: t for s, t in all_tickers_a.items() if s in common_symbols}
        except Exception as e:
            print(f"Failed to fetch tickers from {exchange_a}: {e}")
        try:
            all_tickers_b = await ex_b.fetch_tickers()
            tickers_b = {s: t for s, t in all_tickers_b.items() if s in common_symbols}
        except Exception as e:
            print(f"Failed to fetch tickers from {exchange_b}: {e}")
        
        # Build market list with details
        markets = []
        for symbol in common_symbols:
            market = ex_a.markets.get(symbol, {})
            ticker_a = tickers_a.get(symbol, {})
            ticker_b = tickers_b.get(symbol, {})
            
            price = ticker_a.get('last') or ticker_b.get('last') or 0
            volume_a = ticker_a.get('quoteVolume', 0) or 0
            volume_b = ticker_b.get('quoteVolume', 0) or 0
            change_24h = ticker_a.get('percentage') or ticker_b.get('percentage') or 0
            
            markets.append({
                "symbol": symbol,
                "base": market.get('base'),
                "quote": market.get('quote'),
                "type": market.get('type', 'spot'),
                "price": round(price, 6) if price else None,
                "volume_24h": round(volume_a + volume_b, 2) if (volume_a or volume_b) else None,
                "change_24h": round(change_24h, 2) if change_24h else None,
                "active": True
            })
        
        await ex_a.close()
        await ex_b.close()
        
        # Sort by volume (highest first)
        markets.sort(key=lambda x: x.get('volume_24h') or 0, reverse=True)
        
        return {
            "exchange_a": exchange_a,
            "exchange_b": exchange_b,
            "count": len(markets),
            "total_a": len(symbols_a),
            "total_b": len(symbols_b),
            "markets": markets
        }
    
    except Exception as e:
        return {"error": str(e), "markets": []}


# ============ Live Rates ============

@app.get("/rates", tags=["Rates"])
async def get_live_rates(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get current prices and spreads for all configured symbols"""
    import ccxt.async_support as ccxt
    
    # Get config
    config_result = await db.execute(select(BotConfig).where(BotConfig.id == config_id))
    config = config_result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Get enabled symbols
    symbols_result = await db.execute(
        select(SymbolConfig).where(
            and_(SymbolConfig.config_id == config_id, SymbolConfig.enabled == True)
        )
    )
    symbols = symbols_result.scalars().all()
    
    if not symbols:
        return {"rates": [], "message": "No symbols configured"}
    
    rates = []
    
    try:
        # Initialize exchanges
        ex_a_class = getattr(ccxt, config.exchange_a.lower())
        ex_b_class = getattr(ccxt, config.exchange_b.lower())
        
        ex_a = ex_a_class({'enableRateLimit': True})
        ex_b = ex_b_class({'enableRateLimit': True})
        
        for symbol_config in symbols:
            try:
                # Fetch tickers
                ticker_a = await ex_a.fetch_ticker(symbol_config.symbol)
                ticker_b = await ex_b.fetch_ticker(symbol_config.symbol)
                
                price_a = ticker_a.get('last', 0)
                price_b = ticker_b.get('last', 0)
                
                # Calculate spread
                if price_a > 0 and price_b > 0:
                    spread = ((price_a - price_b) / price_b) * 100
                else:
                    spread = 0
                
                # Determine effective threshold based on strategy mode
                strategy_mode = getattr(config, 'strategy_mode', 'hedge')
                if strategy_mode == 'volume_break_even':
                    # Calculate break-even threshold
                    taker_fee = getattr(config, 'taker_fee', 0.05)
                    slippage = getattr(config, 'slippage', 0.02)
                    use_maker = getattr(config, 'use_maker_orders', False)
                    maker_fee = getattr(config, 'maker_fee', 0.02)
                    fee = maker_fee if use_maker else taker_fee
                    effective_threshold = (fee * 4) + (slippage * 2)
                else:
                    effective_threshold = symbol_config.spread_threshold
                
                # Determine if entry opportunity
                is_opportunity = abs(spread) >= effective_threshold
                
                # Get additional market data
                volume_a = ticker_a.get('quoteVolume', 0) or ticker_a.get('baseVolume', 0) * price_a
                volume_b = ticker_b.get('quoteVolume', 0) or ticker_b.get('baseVolume', 0) * price_b
                change_24h_a = ticker_a.get('percentage', 0) or 0
                change_24h_b = ticker_b.get('percentage', 0) or 0
                
                rates.append({
                    "symbol": symbol_config.symbol,
                    "price_a": round(price_a, 4),
                    "price_b": round(price_b, 4),
                    "bid_a": ticker_a.get('bid'),
                    "ask_a": ticker_a.get('ask'),
                    "bid_b": ticker_b.get('bid'),
                    "ask_b": ticker_b.get('ask'),
                    "spread": round(spread, 4),
                    "spread_threshold": round(effective_threshold, 4),
                    "is_opportunity": is_opportunity,
                    "exchange_a": config.exchange_a,
                    "exchange_b": config.exchange_b,
                    "volume_24h": round((volume_a + volume_b) / 2, 2),
                    "volume_a": round(volume_a, 2),
                    "volume_b": round(volume_b, 2),
                    "change_24h_a": round(change_24h_a, 2),
                    "change_24h_b": round(change_24h_b, 2),
                    "high_a": ticker_a.get('high'),
                    "low_a": ticker_a.get('low'),
                    "position_size_usdt": symbol_config.position_size_usdt
                })
                
                # Cache prices
                for ex_name, price in [(config.exchange_a, price_a), (config.exchange_b, price_b)]:
                    cache_result = await db.execute(
                        select(PriceCache).where(
                            and_(
                                PriceCache.symbol == symbol_config.symbol,
                                PriceCache.exchange == ex_name
                            )
                        )
                    )
                    cache = cache_result.scalar_one_or_none()
                    if cache:
                        cache.last = price
                    else:
                        db.add(PriceCache(symbol=symbol_config.symbol, exchange=ex_name, last=price))
                
            except Exception as e:
                rates.append({
                    "symbol": symbol_config.symbol,
                    "error": str(e)
                })
        
        await ex_a.close()
        await ex_b.close()
        await db.commit()
        
    except Exception as e:
        return {"rates": [], "error": str(e)}
    
    return {
        "rates": rates,
        "exchange_a": config.exchange_a,
        "exchange_b": config.exchange_b,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============ Decision Log (Bot Thinking) ============

@app.get("/decisions", tags=["Decisions"])
async def get_decisions(
    config_id: int = 1,
    symbol: Optional[str] = None,
    decision_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get bot decision log (thought process)"""
    query = select(Decision).where(Decision.config_id == config_id)
    
    if symbol:
        query = query.where(Decision.symbol == symbol)
    if decision_type:
        query = query.where(Decision.decision_type == decision_type)
    
    query = query.order_by(Decision.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    decisions = result.scalars().all()
    
    return [
        {
            "id": d.id,
            "type": d.decision_type.value if d.decision_type else "scan",
            "symbol": d.symbol,
            "price_a": d.price_a,
            "price_b": d.price_b,
            "spread": d.spread,
            "spread_threshold": d.spread_threshold,
            "action": d.action_taken,
            "reason": d.reason,
            "pnl": d.pnl,
            "position_id": d.position_id,
            "timestamp": d.created_at.isoformat() if d.created_at else None
        }
        for d in decisions
    ]


@app.post("/decisions", tags=["Decisions"])
async def log_decision(
    decision_type: str,
    symbol: str,
    price_a: Optional[float] = None,
    price_b: Optional[float] = None,
    spread: Optional[float] = None,
    action_taken: Optional[str] = None,
    reason: Optional[str] = None,
    position_id: Optional[str] = None,
    pnl: Optional[float] = None,
    config_id: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """Log a bot decision (used by bot internally)"""
    try:
        dtype = DecisionType(decision_type)
    except ValueError:
        dtype = DecisionType.SCAN
    
    decision = Decision(
        config_id=config_id,
        decision_type=dtype,
        symbol=symbol,
        price_a=price_a,
        price_b=price_b,
        spread=spread,
        action_taken=action_taken,
        reason=reason,
        position_id=position_id,
        pnl=pnl
    )
    
    db.add(decision)
    await db.commit()
    
    return {"success": True, "id": decision.id}
