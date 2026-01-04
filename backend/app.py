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
        last_activity=None,  # TODO: track last activity
        exchange_a_connected=config.status == BotStatus.RUNNING,
        exchange_b_connected=config.status == BotStatus.RUNNING,
        database_connected=True
    )


# ============ Positions ============

@app.get("/positions", response_model=List[PositionSummary], tags=["Positions"])
async def get_positions(config_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get all open positions"""
    result = await db.execute(
        select(Trade).where(
            and_(Trade.config_id == config_id, Trade.status == TradeStatus.OPEN)
        ).order_by(Trade.open_time.desc())
    )
    trades = result.scalars().all()
    
    positions = []
    for trade in trades:
        positions.append(PositionSummary(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            exchange_a=trade.exchange_a,
            exchange_b=trade.exchange_b,
            entry_price_a=trade.entry_price_a,
            entry_price_b=trade.entry_price_b,
            current_price_a=trade.current_price_a,
            current_price_b=trade.current_price_b,
            amount_usdt=trade.entry_amount_usdt,
            pnl_a=trade.pnl_a,
            pnl_b=trade.pnl_b,
            total_pnl=trade.unrealized_pnl,
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
    
    # Convert to response with hidden API keys
    response = ConfigResponse(
        id=config.id,
        name=config.name,
        mode=config.mode,
        status=config.status,
        virtual_balance=config.virtual_balance,
        current_balance=config.current_balance,
        exchange_a=config.exchange_a,
        exchange_b=config.exchange_b,
        symbol=config.symbol,
        leverage=config.leverage,
        order_type=config.order_type,
        position_size_usdt=config.position_size_usdt,
        position_size_percent=config.position_size_percent,
        stop_loss_percent=config.stop_loss_percent,
        take_profit_percent=config.take_profit_percent,
        max_daily_loss=config.max_daily_loss,
        spread_threshold=config.spread_threshold,
        taker_fee=config.taker_fee,
        maker_fee=config.maker_fee,
        slippage=config.slippage,
        created_at=config.created_at,
        updated_at=config.updated_at,
        has_api_keys_a=bool(config.api_key_a and config.api_secret_a),
        has_api_keys_b=bool(config.api_key_b and config.api_secret_b)
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
    """Get trading summary statistics"""
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
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": total_trades - winning_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "total_fees": round(total_fees, 2),
        "net_pnl": round(total_pnl - total_fees, 2)
    }


# ============ Symbol Configuration ============

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
async def get_available_markets(exchange: str = "binance"):
    """Get available trading pairs from exchange"""
    import ccxt.async_support as ccxt
    
    try:
        exchange_class = getattr(ccxt, exchange.lower())
        ex = exchange_class({'enableRateLimit': True})
        
        await ex.load_markets()
        
        # Filter USDT perpetual futures
        markets = []
        for symbol, market in ex.markets.items():
            if market.get('quote') == 'USDT' and market.get('active', True):
                if market.get('swap') or market.get('future') or market.get('spot'):
                    markets.append({
                        "symbol": symbol,
                        "base": market.get('base'),
                        "quote": market.get('quote'),
                        "type": market.get('type', 'spot'),
                        "active": market.get('active', True)
                    })
        
        await ex.close()
        
        # Sort by symbol
        markets.sort(key=lambda x: x['symbol'])
        
        return {"exchange": exchange, "count": len(markets), "markets": markets[:100]}
    
    except Exception as e:
        return {"exchange": exchange, "error": str(e), "markets": []}


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
                
                # Determine if entry opportunity
                is_opportunity = abs(spread) >= symbol_config.spread_threshold
                
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
                    "spread_threshold": symbol_config.spread_threshold,
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
