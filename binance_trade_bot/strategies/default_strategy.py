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
        current_coin = self.db.get_current_coin()

        # check if we actually have enough of the current coin to bother scouting for jumps
        if current_coin.symbol != self.config.BRIDGE.symbol:
            current_balance = self.manager.get_total_balance(current_coin.symbol)
            min_notional = self.manager.get_min_notional(current_coin.symbol, self.config.BRIDGE.symbol)
            current_price = self.manager.get_ticker_price(current_coin.symbol + self.config.BRIDGE.symbol)
            
            if current_price:
                current_value = current_balance * current_price
                # We use 0.8 * min_notional as a buffer to avoid false positives on small price dips
                # if value is less than $5-8, we consider it "dust" or stuck
                if current_value < (min_notional * 0.8):
                    self.logger.info(f"Stuck state detected: Value of {current_coin.symbol} is too low (${current_value:.2f}). Initializing bridge scout...")
                    self.bridge_scout()
                    return

        # Display on the console, the current coin+Bridge, so users can see *some* activity and not think the bot has
        # stopped. Not logging though to reduce log size.
        print(
            f"{datetime.now()} - CONSOLE - INFO - I am scouting the best trades. "
            f"Current coin: {current_coin + self.config.BRIDGE} ",
            end="\r",
        )

        current_coin_price = self.manager.get_ticker_price(current_coin + self.config.BRIDGE)

        if current_coin_price is None:
            self.logger.info(f"Skipping scouting... current coin {current_coin + self.config.BRIDGE} not found")
            return

        self._jump_to_best_coin(current_coin, current_coin_price)

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
        if self.db.get_current_coin() is None:
            current_coin_symbol = self.config.CURRENT_COIN_SYMBOL

            if not current_coin_symbol:
                self.logger.debug("No starting coin provided. Searching for existing assets...")
                
                # 1. Check if we already hold supported assets (Highest Value Priority)
                assets = []
                for coin in self.config.SUPPORTED_COIN_LIST:
                    balance = self.manager.get_total_balance(coin) # Use Total Balance (Free + Locked)
                    if balance > 0:
                        price = self.manager.get_ticker_price(coin + self.config.BRIDGE.symbol)
                        if price:
                            value = balance * price
                            if value >= 1.0:  # Ignore assets worth less than $1
                                assets.append({"symbol": coin, "value": value})
                        else:
                            # If price fetch fails, we skip it for safety during initialization
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
                        return # Exit this run, scheduler will retry

            if current_coin_symbol:
                self.logger.info(f"Setting initial coin to {current_coin_symbol}")

                if current_coin_symbol not in self.config.SUPPORTED_COIN_LIST:
                    self.logger.error("Invalid Coin: A proper coin name must be provided")
                    sys.exit(1)
                
                self.db.set_current_coin(current_coin_symbol)

                # if we didn't have a configuration, we selected a coin at random... Buy it so we can start trading.
                if self.config.CURRENT_COIN_SYMBOL == "":
                    current_coin = self.db.get_current_coin()
                    
                    # Logic to buy only if we don't already have it (for the USDT case)
                    # For assets we found, we likely already have them, so this check avoids re-buying
                    current_balance = self.manager.get_currency_balance(current_coin.symbol)
                    price = self.manager.get_ticker_price(current_coin.symbol + self.config.BRIDGE.symbol)
                    val_in_bridge = current_balance * price if price else 0

                    if val_in_bridge < 10.0: # If we have less than $10 worth, assume we need to buy more (or it was a fresh random pick)
                         self.logger.info(f"Purchasing {current_coin} to begin trading")
                         self.manager.buy_alt(current_coin, self.config.BRIDGE)
                    
                    self.logger.info("Ready to start trading")
