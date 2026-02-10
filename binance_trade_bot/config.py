# Config consts
import configparser
import os

from .models import Coin

CFG_FL_NAME = "user.cfg"
USER_CFG_SECTION = "binance_user_config"


class Config:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    def __init__(self):
        # Init config
        config = configparser.ConfigParser()
        config["DEFAULT"] = {
            "bridge": "USDT",
            "use_margin": "no",
            "scout_multiplier": "5",
            "scout_margin": "0.8",
            "scout_sleep_time": "5",
            "hourToKeepScoutHistory": "1",
            "tld": "com",
            "strategy": "default",
            "sell_timeout": "0",
            "buy_timeout": "0",
            "testnet": False,
            "dry_run": False,
        }

        if not os.path.exists(CFG_FL_NAME):
            print("No configuration file (user.cfg) found! See README. Assuming default config...")
            config[USER_CFG_SECTION] = {}
        else:
            config.read(CFG_FL_NAME)

        def get_val(section, key, default=None, is_bool=False):
            # 1. Check environment variable (UPPERCASE)
            env_var = key.upper()
            env_val = os.environ.get(env_var)
            
            # Map specific keys if needed (e.g. bridge -> BRIDGE_SYMBOL)
            if key == "bridge" and not env_val: env_val = os.environ.get("BRIDGE_SYMBOL")
            if key == "api_key" and not env_val: env_val = os.environ.get("API_KEY")
            if key == "api_secret_key" and not env_val: env_val = os.environ.get("API_SECRET_KEY")
            
            if env_val is not None:
                if is_bool:
                    return str(env_val).lower() in ("true", "1", "yes")
                return env_val

            # 2. Check config file
            try:
                if is_bool:
                    return config.getboolean(section, key)
                return config.get(section, key)
            except:
                return default

        self.BRIDGE_SYMBOL = get_val(USER_CFG_SECTION, "bridge", "USDT")
        self.BRIDGE = Coin(self.BRIDGE_SYMBOL, False)
        self.TESTNET = get_val(USER_CFG_SECTION, "testnet", False, is_bool=True)
        self.DRY_RUN = get_val(USER_CFG_SECTION, "dry_run", False, is_bool=True)

        # Prune settings
        self.SCOUT_HISTORY_PRUNE_TIME = float(
            get_val(USER_CFG_SECTION, "hourToKeepScoutHistory", 1)
        )

        # Get config for scout
        self.SCOUT_MULTIPLIER = float(get_val(USER_CFG_SECTION, "scout_multiplier", 5))
        self.SCOUT_SLEEP_TIME = int(get_val(USER_CFG_SECTION, "scout_sleep_time", 5))

        # Get config for binance
        self.BINANCE_API_KEY = get_val(USER_CFG_SECTION, "api_key")
        self.BINANCE_API_SECRET_KEY = get_val(USER_CFG_SECTION, "api_secret_key")
        self.BINANCE_TLD = get_val(USER_CFG_SECTION, "tld", "com")

        # Get supported coin list from the environment
        supported_coin_list = [
            coin.strip() for coin in os.environ.get("SUPPORTED_COIN_LIST", "").split() if coin.strip()
        ]
        # Get supported coin list from supported_coin_list file
        if not supported_coin_list and os.path.exists("supported_coin_list"):
            with open("supported_coin_list") as rfh:
                for line in rfh:
                    line = line.strip()
                    if not line or line.startswith("#") or line in supported_coin_list:
                        continue
                    supported_coin_list.append(line)
        self.SUPPORTED_COIN_LIST = supported_coin_list

        self.CURRENT_COIN_SYMBOL = get_val(USER_CFG_SECTION, "current_coin", "")

        self.STRATEGY = get_val(USER_CFG_SECTION, "strategy", "default")

        self.SELL_TIMEOUT = get_val(USER_CFG_SECTION, "sell_timeout", "0")
        self.BUY_TIMEOUT = get_val(USER_CFG_SECTION, "buy_timeout", "0")

        self.USE_MARGIN = get_val(USER_CFG_SECTION, "use_margin", "no")
        self.SCOUT_MARGIN = float(get_val(USER_CFG_SECTION, "scout_margin", "0.8"))
