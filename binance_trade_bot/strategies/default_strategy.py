import random
import sys
import time
from datetime import datetime

from binance_trade_bot.auto_trader import AutoTrader


class Strategy(AutoTrader):
    def initialize(self):
        super().initialize()
        self.initialize_current_coin()

    def scout(self):
        """
        Scout for potential jumps from the current coin to another coin
        """
        try:
            current_coin = self.db.get_current_coin()
            if current_coin is None:
                self.logger.warning("No current coin found in database. Initializing...")
                self.initialize_current_coin()
                current_coin = self.db.get_current_coin()
                if current_coin is None:
                    return

            self.logger.info(
                f"CONSOLE - INFO - I am scouting the best trades. "
                f"Current coin: {current_coin + self.config.BRIDGE} "
            )

            current_coin_price = self.manager.get_ticker_price(current_coin + self.config.BRIDGE)

            if current_coin_price is None:
                self.logger.info(f"Skipping scouting... current coin {current_coin + self.config.BRIDGE} not found")
                return

            self._jump_to_best_coin(current_coin, current_coin_price)
        except Exception as e:  # pylint: disable=broad-except
            # Handle connection errors gracefully (proxy failures, network issues, etc.)
            error_msg = str(e)
            # Check for connection error patterns (case-insensitive matching)
            connection_error_keywords = [
                'proxy', 'connectionrefused', 'newconnectionerror',
                'timeout', 'connectionerror', 'econnrefused',
                'read timed out', 'connect timeout',
                'max retries exceeded', 'remote disconnected'
            ]
            is_connection_error = any(keyword.lower() in error_msg.lower() for keyword in connection_error_keywords)

            if is_connection_error:
                self.logger.warning(f"Scouting failed due to connection error: {e}")
                self.logger.info("Scouting will retry on next scheduled run. Proxy refresh may be in progress.")
            else:
                # Re-raise non-connection errors
                self.logger.error(f"Scouting failed with unexpected error: {e}")
                raise

    def bridge_scout(self):
        current_coin = self.db.get_current_coin()
        if self.manager.get_currency_balance(current_coin.symbol) > self.manager.get_min_notional(
            current_coin.symbol, self.config.BRIDGE.symbol
        ):
            # Only scout if we don't have enough of the current coin
            return
        new_coin = super().bridge_scout()
        if new_coin is not None:
            self.db.set_current_coin(new_coin)

    def initialize_current_coin(self):
        """
        Decide what is the current coin, and set it up in the DB.
        """
        while self.db.get_current_coin() is None:
            current_coin_symbol = self.config.CURRENT_COIN_SYMBOL

            if not current_coin_symbol:
                self.logger.debug("No starting coin provided. Searching for existing assets...")
                
                # 1. Check if we already hold supported assets (Highest Value Priority)
                assets = []
                for coin in self.config.SUPPORTED_COIN_LIST:
                    balance = self.manager.get_currency_balance(coin)
                    if balance > 0:
                        price = self.manager.get_ticker_price(coin + self.config.BRIDGE.symbol)
                        if price:
                            value = balance * price
                            if value >= 1.0:  # Ignore assets worth less than $1
                                assets.append({"symbol": coin, "value": value})
                        else:
                            # If price fetch fails, we skip it for safety during initialization
                            # unless it's a significant balance we can't value yet.
                            pass
                
                if assets:
                    # Pick the coin with the highest current value
                    highest_asset = max(assets, key=lambda x: x['value'])
                    self.logger.info(f"Asset Selection: Prioritizing {highest_asset['symbol']} (${highest_asset['value']:.2f})")
                    current_coin_symbol = highest_asset['symbol']
                
                # 2. If no assets, check for bridge funds (USDT)
                if not current_coin_symbol:
                    bridge_balance = self.manager.get_currency_balance(self.config.BRIDGE.symbol)
                    # Use a small coin for min_notional check
                    min_notional = 10.0 # Default fallback
                    try:
                        min_notional = self.manager.get_min_notional(self.config.SUPPORTED_COIN_LIST[0], self.config.BRIDGE.symbol)
                    except:
                        pass
                    
                    if bridge_balance >= min_notional:
                        self.logger.info(f"Found {bridge_balance} {self.config.BRIDGE.symbol}. Selecting a starting asset...")
                        current_coin_symbol = random.choice(self.config.SUPPORTED_COIN_LIST)
                    else:
                        self.logger.warning(f"⚠️ No funds detected in Spot wallet (Current USDT: {bridge_balance}).")
                        self.logger.warning("Please transfer at least 20 USDT to your 'Spot' wallet on Binance.")
                        self.logger.info("Bot will retry in 60 seconds...")
                        time.sleep(60)
                        continue

            self.logger.info(f"Setting initial coin to {current_coin_symbol}")

            if current_coin_symbol not in self.config.SUPPORTED_COIN_LIST:
                self.logger.error("Since there is no backup file, a proper coin name must be provided at init")
                sys.exit(1)
            
            self.db.set_current_coin(current_coin_symbol)

            # if we didn't have a configuration, we selected a coin at random... Buy it so we can start trading.
            if self.config.CURRENT_COIN_SYMBOL == "":
                current_coin = self.db.get_current_coin()
                # Check if we actually need to buy it (current balance might be empty or too small to trade)
                current_balance = self.manager.get_currency_balance(current_coin.symbol)
                min_notional = self.manager.get_min_notional(current_coin.symbol, self.config.BRIDGE.symbol)
                
                if current_balance < (min_notional / self.manager.get_ticker_price(current_coin.symbol + self.config.BRIDGE.symbol)):
                    self.logger.info(f"Purchasing {current_coin} to begin trading")
                    self.manager.buy_alt(current_coin, self.config.BRIDGE)
                self.logger.info("Ready to start trading")
