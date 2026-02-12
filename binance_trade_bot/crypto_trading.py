#!python3
import time
from datetime import datetime

from .binance_api_manager import BinanceAPIManager
from .config import Config
from .database import Database
from .logger import Logger
from .scheduler import SafeScheduler
from .strategies import get_strategy
from .dashboard import start_dashboard, bot_status


def main():
    logger = Logger()
    logger.info("Starting")

    config = Config()
    db = Database(logger, config)
    manager = BinanceAPIManager(config, db, logger, config.TESTNET)
    # check if we can access API feature that require valid config
    try:
        _ = manager.get_account()
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Couldn't access Binance API - API keys may be wrong or lack sufficient permissions")
        logger.error(e)
        return
    strategy = get_strategy(config.STRATEGY)
    if strategy is None:
        logger.error("Invalid strategy name")
        return
    trader = strategy(manager, db, logger, config)
    logger.info(f"Chosen strategy: {config.STRATEGY}")

    logger.info("Creating database schema if it doesn't already exist")
    db.create_database()

    db.set_coins(config.SUPPORTED_COIN_LIST)
    db.migrate_old_state()

    trader.initialize()

    # Start the web dashboard for Render and visualization
    start_dashboard()
    bot_status["is_active"] = True
    bot_status["bridge"] = config.BRIDGE_SYMBOL

    def sync_dashboard():
        try:
            current_coin = db.get_current_coin()
            if current_coin:
                bot_status["current_coin"] = current_coin.symbol
                balance = manager.get_total_balance(current_coin.symbol)
                
                # Calculate value in Bridge currency (e.g. USDT)
                if current_coin.symbol != config.BRIDGE_SYMBOL:
                    price = manager.get_ticker_price(current_coin.symbol + config.BRIDGE_SYMBOL)
                    if price:
                        bot_status["balance"] = balance * price
                    else:
                        bot_status["balance"] = 0.0 # Price not found
                else:
                    bot_status["balance"] = balance
            
            # Get last 5 trades
            with db.db_session() as session:
                from .models import Trade
                recent_trades = session.query(Trade).order_by(Trade.datetime.desc()).limit(5).all()
                bot_status["trades"] = [
                    {
                        "time": t.datetime.strftime("%H:%M:%S"),
                        "pair": f"{t.alt_coin_id}/{t.crypto_coin_id}",
                        "type": "SELL" if t.selling else "BUY",
                        "price": f"{t.crypto_trade_amount / t.alt_trade_amount:.8f}" if (t.alt_trade_amount and t.crypto_trade_amount) else "Pending"
                    } for t in recent_trades
                ]
            bot_status["last_update"] = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            logger.warning(f"Dashboard sync failed: {e}")

    schedule = SafeScheduler(logger)
    schedule.every(config.SCOUT_SLEEP_TIME).seconds.do(trader.scout).tag("scouting")
    schedule.every(1).minutes.do(trader.update_values).tag("updating value history")
    schedule.every(30).seconds.do(sync_dashboard).tag("syncing dashboard")
    schedule.every(1).minutes.do(db.prune_scout_history).tag("pruning scout history")
    schedule.every(1).hours.do(db.prune_value_history).tag("pruning value history")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    finally:
        manager.stream_manager.close()