from datetime import datetime

from binance_trade_bot.auto_trader import AutoTrader
from binance_trade_bot.safe_print import safe_print


class Strategy(AutoTrader):
    def scout(self):
        """
        Scout for potential jumps from the current coin to another coin
        """
        try:
            have_coin = False

            # last coin bought
            current_coin = self.db.get_current_coin()
            current_coin_symbol = ""

            if current_coin is not None:
                current_coin_symbol = current_coin.symbol

            for coin in self.db.get_coins():
                current_coin_balance = self.manager.get_currency_balance(coin.symbol)
                coin_price = self.manager.get_ticker_price(coin + self.config.BRIDGE)

                if coin_price is None:
                    self.logger.info(f"Skipping scouting... current coin {coin + self.config.BRIDGE} not found")
                    continue

                min_notional = self.manager.get_min_notional(coin.symbol, self.config.BRIDGE.symbol)

                if coin.symbol != current_coin_symbol and coin_price * current_coin_balance < min_notional:
                    continue

                have_coin = True

                # Display on the console, the current coin+Bridge, so users can see *some* activity and not think the bot
                # has stopped. Not logging though to reduce log size.
                safe_print(
                    f"{datetime.now()} - CONSOLE - INFO - I am scouting the best trades. "
                    f"Current coin: {coin + self.config.BRIDGE} ",
                    end="\r",
                )

                self._jump_to_best_coin(coin, coin_price)

            if not have_coin:
                self.bridge_scout()
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
