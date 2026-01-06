"""
HedgeBot - Main Entry Point
Delta-Neutral Trading Bot for Cryptocurrency Exchanges
With Database Integration
"""
import asyncio
import os
import sys
import signal
import logging
from datetime import datetime
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('hedgebot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("HedgeBot")

# Reduce noise from ccxt
logging.getLogger('ccxt').setLevel(logging.WARNING)


class HedgeBot:
    """
    Main HedgeBot application.
    Coordinates exchanges, strategy, risk management, and database.
    """
    
    def __init__(self, config_id: int = 1):
        self.config_id = config_id
        self.running = False
        self.start_time: Optional[datetime] = None
        
        # Components (initialized in setup)
        self.ex_a = None
        self.ex_b = None
        self.strategy = None
        self.risk_manager = None
        self.db_service = None
        
        # Configuration (loaded from DB or environment)
        self.config: Dict = {}
        
        # Position ID to DB trade_id mapping
        self._position_to_trade_id: Dict[str, str] = {}
    
    async def setup(self):
        """Initialize all components"""
        from bot.exchange import ExchangeManager
        from bot.strategy import Strategy
        from bot.risk_manager import RiskManager, RiskLimits
        from bot.db_service import DatabaseService
        
        logger.info("=" * 60)
        logger.info("HedgeBot Initializing...")
        logger.info("=" * 60)
        
        # Initialize database connection
        self.db_service = DatabaseService()
        db_connected = await self.db_service.connect()
        
        if db_connected:
            logger.info("✓ Database connected")
            # Try to load config from database
            db_config = await self.db_service.load_config(self.config_id)
            if db_config:
                self.config = db_config
                logger.info(f"✓ Config loaded from database (ID: {self.config_id})")
            else:
                logger.info("Config not found in DB, using environment variables")
                self._load_config_from_env()
        else:
            logger.warning("⚠ Database not available, using environment variables")
            self._load_config_from_env()
        
        # Log configuration
        logger.info(f"Mode: {self.config.get('mode', 'simulation').upper()}")
        logger.info(f"Exchanges: {self.config.get('exchange_a')} / {self.config.get('exchange_b')}")
        logger.info(f"Symbol: {self.config.get('symbol')}")
        logger.info(f"Position Size: {self.config.get('position_size_usdt')} USDT x{self.config.get('leverage')}")
        logger.info("-" * 60)
        
        is_simulation = self.config.get('mode') == 'simulation'
        
        # Initialize Exchange A (Long side)
        self.ex_a = ExchangeManager(
            exchange_id=self.config.get('exchange_a', 'binance'),
            api_key=self.config.get('api_key_a') if not is_simulation else None,
            secret=self.config.get('api_secret_a') if not is_simulation else None,
            simulation_mode=is_simulation,
            taker_fee=self.config.get('taker_fee', 0.1),
            maker_fee=self.config.get('maker_fee', 0.05),
            slippage=self.config.get('slippage', 0.05)
        )
        
        # Initialize Exchange B (Short side)
        self.ex_b = ExchangeManager(
            exchange_id=self.config.get('exchange_b', 'bybit'),
            api_key=self.config.get('api_key_b') if not is_simulation else None,
            secret=self.config.get('api_secret_b') if not is_simulation else None,
            simulation_mode=is_simulation,
            taker_fee=self.config.get('taker_fee', 0.1),
            maker_fee=self.config.get('maker_fee', 0.05),
            slippage=self.config.get('slippage', 0.05)
        )
        
        # Connect to exchanges
        logger.info(f"Connecting to {self.config.get('exchange_a')}...")
        if not await self.ex_a.connect():
            raise RuntimeError(f"Failed to connect to {self.config.get('exchange_a')}")
        logger.info(f"✓ {self.config.get('exchange_a')} connected")
        
        logger.info(f"Connecting to {self.config.get('exchange_b')}...")
        if not await self.ex_b.connect():
            raise RuntimeError(f"Failed to connect to {self.config.get('exchange_b')}")
        logger.info(f"✓ {self.config.get('exchange_b')} connected")
        
        # Initialize Strategy
        self.strategy = Strategy(
            exchange_a=self.ex_a,
            exchange_b=self.ex_b,
            symbol=self.config.get('symbol', 'BTC/USDT'),
            position_size_usdt=self.config.get('position_size_usdt', 100.0),
            leverage=self.config.get('leverage', 1),
            spread_threshold=self.config.get('spread_threshold', 0.5),
            stop_loss_percent=self.config.get('stop_loss_percent', 2.0),
            take_profit_percent=self.config.get('take_profit_percent', 5.0),
            order_type=self.config.get('order_type', 'market')
        )
        
        # Set callbacks for database integration
        self.strategy.on_position_opened = self._on_position_opened
        self.strategy.on_position_closed = self._on_position_closed
        self.strategy.on_position_updated = self._on_position_updated
        
        # Initialize Risk Manager
        risk_limits = RiskLimits(
            stop_loss_percent=self.config.get('stop_loss_percent', 2.0),
            take_profit_percent=self.config.get('take_profit_percent', 5.0),
            global_stop_loss=self.config.get('max_daily_loss', 500.0),
            global_take_profit=1000.0,
            max_daily_loss=self.config.get('max_daily_loss', 500.0),
            max_open_positions=5,
            max_position_size_usdt=self.config.get('position_size_usdt', 100.0) * 10
        )
        
        self.risk_manager = RiskManager(
            strategy=self.strategy,
            limits=risk_limits,
            check_interval=1.0
        )
        
        self.risk_manager.on_stop_loss = self._on_stop_loss
        self.risk_manager.on_take_profit = self._on_take_profit
        self.risk_manager.on_trading_halted = self._on_trading_halted
        
        # Update status in database
        if self.db_service.is_connected:
            await self.db_service.update_config_status(self.config_id, "running")
            await self.db_service.log_info(
                f"Bot started in {self.config.get('mode')} mode",
                category="system",
                config_id=self.config_id
            )
        
        logger.info("=" * 60)
        logger.info("Setup complete!")
        logger.info("=" * 60)
    
    def _load_config_from_env(self):
        """Load configuration from environment variables"""
        self.config = {
            "id": 0,
            "mode": os.getenv("TRADING_MODE", "simulation"),
            "exchange_a": os.getenv("EXCHANGE_A", "binance"),
            "exchange_b": os.getenv("EXCHANGE_B", "bybit"),
            "symbol": os.getenv("SYMBOL", "BTC/USDT"),
            "api_key_a": os.getenv("EXCHANGE_A_API_KEY"),
            "api_secret_a": os.getenv("EXCHANGE_A_SECRET"),
            "api_key_b": os.getenv("EXCHANGE_B_API_KEY"),
            "api_secret_b": os.getenv("EXCHANGE_B_SECRET"),
            "position_size_usdt": float(os.getenv("POSITION_SIZE_USDT", "100")),
            "leverage": int(os.getenv("LEVERAGE", "1")),
            "spread_threshold": float(os.getenv("SPREAD_THRESHOLD", "0.5")),
            "stop_loss_percent": float(os.getenv("STOP_LOSS_PERCENT", "2.0")),
            "take_profit_percent": float(os.getenv("TAKE_PROFIT_PERCENT", "5.0")),
            "max_daily_loss": float(os.getenv("MAX_DAILY_LOSS", "500.0")),
            "taker_fee": float(os.getenv("TAKER_FEE", "0.1")),
            "maker_fee": float(os.getenv("MAKER_FEE", "0.05")),
            "slippage": float(os.getenv("SLIPPAGE", "0.05")),
            "order_type": "market",
            "virtual_balance": float(os.getenv("VIRTUAL_BALANCE", "10000")),
            "current_balance": float(os.getenv("VIRTUAL_BALANCE", "10000")),
            "check_interval": float(os.getenv("CHECK_INTERVAL", "5")),
            "auto_trade": os.getenv("AUTO_TRADE", "false").lower() == "true",
        }
    
    async def _on_position_opened(self, position):
        """Callback when a position is opened - save to DB"""
        logger.info(
            f"📈 POSITION OPENED: {position.position_id} | "
            f"{position.symbol} | Size: {position.entry_amount_usdt} USDT"
        )
        
        # Save to database
        if self.db_service and self.db_service.is_connected:
            trade_id = await self.db_service.save_trade(
                config_id=self.config_id,
                position=position,
                mode=self.config.get('mode', 'simulation')
            )
            
            if trade_id:
                self._position_to_trade_id[position.position_id] = trade_id
                await self.db_service.log_trade(
                    f"Position opened: {position.symbol} @ A:{position.entry_price_a:.2f} B:{position.entry_price_b:.2f}",
                    trade_id=trade_id,
                    config_id=self.config_id
                )
    
    async def _on_position_closed(self, position):
        """Callback when a position is closed - update in DB"""
        logger.info(
            f"📉 POSITION CLOSED: {position.position_id} | "
            f"Reason: {position.close_reason} | PnL: {position.realized_pnl:.4f} USDT"
        )
        
        # Update in database
        if self.db_service and self.db_service.is_connected:
            trade_id = self._position_to_trade_id.get(position.position_id)
            
            if trade_id:
                await self.db_service.close_trade(
                    trade_id=trade_id,
                    exit_price_a=position.exit_price_a,
                    exit_price_b=position.exit_price_b,
                    pnl_a=position.pnl_a,
                    pnl_b=position.pnl_b,
                    pnl_net=position.realized_pnl,
                    fees_paid=position.fees_paid,
                    close_reason=position.close_reason or "unknown"
                )
                
                await self.db_service.log_trade(
                    f"Position closed: {position.close_reason}, PnL: {position.realized_pnl:.4f}",
                    trade_id=trade_id,
                    config_id=self.config_id
                )
                
                # Update balance
                new_balance = self.config.get('current_balance', 10000) + position.realized_pnl
                self.config['current_balance'] = new_balance
                await self.db_service.update_balance(self.config_id, new_balance)
                
                # Clean up mapping
                del self._position_to_trade_id[position.position_id]
    
    async def _on_position_updated(self, position):
        """Callback when position prices are updated"""
        if self.db_service and self.db_service.is_connected:
            trade_id = self._position_to_trade_id.get(position.position_id)
            
            if trade_id:
                await self.db_service.update_trade(
                    trade_id=trade_id,
                    current_price_a=position.current_price_a,
                    current_price_b=position.current_price_b,
                    unrealized_pnl=position.unrealized_pnl,
                    pnl_a=position.pnl_a,
                    pnl_b=position.pnl_b
                )
    
    async def _on_stop_loss(self, position):
        """Callback when stop-loss is triggered"""
        logger.warning(f"🛑 STOP-LOSS: {position.position_id} | PnL: {position.realized_pnl:.4f}")
        
        if self.db_service and self.db_service.is_connected:
            await self.db_service.log_warning(
                f"Stop-loss triggered: {position.position_id}, PnL: {position.realized_pnl:.4f}",
                category="risk",
                config_id=self.config_id
            )
    
    async def _on_take_profit(self, position):
        """Callback when take-profit is triggered"""
        logger.info(f"💰 TAKE-PROFIT: {position.position_id} | PnL: {position.realized_pnl:.4f}")
        
        if self.db_service and self.db_service.is_connected:
            await self.db_service.log_info(
                f"Take-profit triggered: {position.position_id}, PnL: {position.realized_pnl:.4f}",
                category="risk",
                config_id=self.config_id
            )
    
    async def _on_trading_halted(self, reason):
        """Callback when trading is halted"""
        logger.critical(f"⛔ TRADING HALTED: {reason}")
        
        if self.db_service and self.db_service.is_connected:
            await self.db_service.log_error(
                f"Trading halted: {reason}",
                category="risk",
                config_id=self.config_id
            )
            await self.db_service.update_config_status(self.config_id, "stopped")
    
    async def run(self):
        """Main bot loop with multi-symbol and strategy mode support"""
        from bot.volume_strategy import VolumeStrategy, VolumeStrategyConfig, CloseDecision
        from datetime import timedelta
        
        self.running = True
        self.start_time = datetime.utcnow()
        
        # Start risk manager
        await self.risk_manager.start()
        
        logger.info("Bot is running. Press Ctrl+C to stop.")
        
        check_interval = self.config.get('check_interval', 5.0)
        strategy_mode = self.config.get('strategy_mode', 'hedge')
        
        # Initialize VolumeStrategy if in volume mode
        volume_strategy = None
        if strategy_mode == 'volume_break_even':
            vol_config = VolumeStrategyConfig(
                min_hold_time_minutes=self.config.get('min_hold_time_minutes', 60),
                max_hold_time_minutes=self.config.get('max_hold_time_minutes', 480),
                close_only_if_profitable=self.config.get('close_only_if_profitable', True),
                min_entry_spread_percent=self.config.get('min_entry_spread_percent', 0.30),
                emergency_stop_loss_percent=self.config.get('emergency_stop_loss_percent', 2.0),
                taker_fee_percent=self.config.get('taker_fee', 0.05),
                maker_fee_percent=self.config.get('maker_fee', 0.02),
                slippage_percent=self.config.get('slippage', 0.02),
                use_maker_orders=self.config.get('use_maker_orders', False)
            )
            volume_strategy = VolumeStrategy(self.ex_a, self.ex_b, vol_config)
            logger.info(f"📊 Volume Farming mode: break-even spread = {vol_config.break_even_spread:.4f}%")
        
        # Track open positions with their open times
        open_positions: Dict[str, dict] = {}  # symbol -> {open_time, entry_prices, pnl...}
        
        # Load symbols from database
        symbols = []
        if self.db_service and self.db_service.is_connected:
            symbols = await self.db_service.load_symbols(self.config_id)
            if symbols:
                logger.info(f"Loaded {len(symbols)} symbols from database")
            else:
                symbols = [{
                    "symbol": self.config.get('symbol', 'BTC/USDT'),
                    "spread_threshold": self.config.get('spread_threshold', 0.5),
                    "position_size_usdt": self.config.get('position_size_usdt', 100),
                    "leverage": self.config.get('leverage', 1),
                }]
                logger.info("No symbols in DB, using default from config")
        else:
            symbols = [{
                "symbol": self.config.get('symbol', 'BTC/USDT'),
                "spread_threshold": self.config.get('spread_threshold', 0.5),
                "position_size_usdt": self.config.get('position_size_usdt', 100),
            }]
        
        while self.running:
            try:
                # Scan each symbol
                for sym_config in symbols:
                    symbol = sym_config.get('symbol')
                    position_size = sym_config.get('position_size_usdt', 100)
                    leverage = sym_config.get('leverage', 1)
                    
                    try:
                        # Get prices from both exchanges
                        ticker_a = await self.ex_a.fetch_ticker(symbol)
                        ticker_b = await self.ex_b.fetch_ticker(symbol)
                        
                        if not ticker_a or not ticker_b:
                            continue
                        
                        price_a = ticker_a.last
                        price_b = ticker_b.last
                        
                        if not price_a or not price_b:
                            continue
                        
                        # Calculate spread
                        spread = ((price_a - price_b) / price_b) * 100
                        
                        # Check for existing position
                        if symbol in open_positions:
                            pos = open_positions[symbol]
                            elapsed = datetime.utcnow() - pos['open_time']
                            
                            # Calculate current PnL
                            pnl_a = (price_a - pos['entry_price_a']) * pos['amount']
                            pnl_b = (pos['entry_price_b'] - price_b) * pos['amount']
                            net_pnl = pnl_a + pnl_b - pos.get('fees', 0)
                            pnl_percent = (net_pnl / position_size) * 100
                            
                            # Decide if should close
                            if volume_strategy:
                                decision, reason = volume_strategy.should_close(
                                    pos, pnl_percent, elapsed
                                )
                                
                                if decision != CloseDecision.HOLD:
                                    # Close trade in database
                                    trade_id = pos.get('trade_id')
                                    if trade_id:
                                        await self.db_service.close_trade(
                                            trade_id=trade_id,
                                            exit_price_a=price_a,
                                            exit_price_b=price_b,
                                            pnl_a=pnl_a,
                                            pnl_b=pnl_b,
                                            pnl_net=net_pnl,
                                            fees_paid=pos.get('fees', 0),
                                            close_reason=decision.value
                                        )
                                    
                                    await self.db_service.log_decision(
                                        config_id=self.config_id,
                                        decision_type="exit",
                                        symbol=symbol,
                                        price_a=price_a,
                                        price_b=price_b,
                                        spread=round(spread, 4),
                                        action_taken=decision.value,
                                        reason=reason,
                                        pnl=round(net_pnl, 4),
                                        position_id=trade_id
                                    )
                                    
                                    volume = volume_strategy.calculate_volume_generated(position_size, leverage)
                                    hold_seconds = int(elapsed.total_seconds())
                                    
                                    logger.info(
                                        f"📤 {symbol} CLOSE: {decision.value} | "
                                        f"PnL: ${net_pnl:.2f} | Hold: {hold_seconds}s | Vol: ${volume}"
                                    )
                                    
                                    del open_positions[symbol]
                                else:
                                    # Still holding
                                    if elapsed.total_seconds() % 60 < check_interval:
                                        logger.debug(f"⏳ {symbol} HOLD: {reason}")
                            continue
                        
                        # No position - check for entry
                        if volume_strategy:
                            # Volume mode: use break-even logic
                            should_enter, reason = await volume_strategy.should_enter(symbol, abs(spread))
                        else:
                            # Classic hedge mode
                            threshold = sym_config.get('spread_threshold', 0.5)
                            should_enter = abs(spread) >= threshold
                            reason = f"Spread {spread:.4f}% vs threshold {threshold}%"
                        
                        if should_enter and self.db_service and self.db_service.is_connected:
                            can_open, risk_reason = self.risk_manager.can_open_position(position_size)
                            
                            if can_open:
                                # Calculate trade params
                                avg_price = (price_a + price_b) / 2
                                amount = position_size / avg_price
                                # Total fees: 4 transactions (open long, open short, close long, close short)
                                fee_rate = self.config.get('taker_fee', 0.05) / 100
                                fees = position_size * fee_rate * 4  # Entry + Exit fees
                                
                                # Save trade to database
                                trade_id = await self.db_service.create_trade_simple(
                                    config_id=self.config_id,
                                    symbol=symbol,
                                    exchange_a=self.ex_a.exchange_id,
                                    exchange_b=self.ex_b.exchange_id,
                                    entry_price_a=price_a,
                                    entry_price_b=price_b,
                                    amount=amount,
                                    amount_usdt=position_size,
                                    leverage=leverage,
                                    fees=fees,
                                    mode=self.config.get('mode', 'simulation')
                                )
                                
                                # Track in memory with trade_id
                                open_positions[symbol] = {
                                    'trade_id': trade_id,
                                    'open_time': datetime.utcnow(),
                                    'entry_price_a': price_a,
                                    'entry_price_b': price_b,
                                    'amount': amount,
                                    'position_size': position_size,
                                    'leverage': leverage,
                                    'fees': fees
                                }
                                
                                await self.db_service.log_decision(
                                    config_id=self.config_id,
                                    decision_type="entry",
                                    symbol=symbol,
                                    price_a=price_a,
                                    price_b=price_b,
                                    spread=round(spread, 4),
                                    action_taken="open_position",
                                    reason=reason,
                                    position_id=trade_id
                                )
                                
                                logger.info(
                                    f"📥 {symbol} ENTRY | Spread: {spread:.4f}% | "
                                    f"A: ${price_a:.2f} B: ${price_b:.2f} | ID: {trade_id[:8]}"
                                )
                            else:
                                await self.db_service.log_decision(
                                    config_id=self.config_id,
                                    decision_type="skip",
                                    symbol=symbol,
                                    price_a=price_a,
                                    price_b=price_b,
                                    spread=round(spread, 4),
                                    action_taken="none",
                                    reason=f"Risk check: {risk_reason}"
                                )
                    
                    except Exception as sym_error:
                        if self.db_service and self.db_service.is_connected:
                            await self.db_service.log_decision(
                                config_id=self.config_id,
                                decision_type="error",
                                symbol=symbol,
                                reason=str(sym_error)
                            )
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                if self.db_service and self.db_service.is_connected:
                    await self.db_service.log_error(str(e), category="system", config_id=self.config_id)
                await asyncio.sleep(check_interval)
        
        logger.info("Bot loop stopped.")
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down...")
        self.running = False
        
        # Stop risk manager
        if self.risk_manager:
            await self.risk_manager.stop()
        
        # Close all positions if needed
        if self.strategy:
            open_positions = len(self.strategy.get_open_positions())
            if open_positions > 0:
                logger.warning(f"Closing {open_positions} open positions...")
                await self.strategy.close_all_positions("shutdown")
        
        # Update database status
        if self.db_service and self.db_service.is_connected:
            await self.db_service.update_config_status(self.config_id, "stopped")
            await self.db_service.log_info("Bot stopped", category="system", config_id=self.config_id)
            await self.db_service.disconnect()
        
        # Close exchange connections
        if self.ex_a:
            await self.ex_a.close()
        if self.ex_b:
            await self.ex_b.close()
        
        logger.info("Shutdown complete.")


async def main():
    """Entry point"""
    # Get config ID from environment or use default
    config_id = int(os.getenv("CONFIG_ID", "1"))
    
    bot = HedgeBot(config_id=config_id)
    
    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(bot.shutdown())
    
    # Try to set signal handlers (may not work on Windows in all cases)
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass
    
    try:
        await bot.setup()
        await bot.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        raise
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
