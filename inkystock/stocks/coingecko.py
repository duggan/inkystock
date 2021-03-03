import logging
from datetime import datetime, timedelta

from pycoingecko import CoinGeckoAPI
from inkystock.config import Config
from inkystock.stocks.base import Stock, Point, Series


log = logging.getLogger("inkystock")


class CoinGecko(Stock):
    PROVIDER_CURRENCY = 'USD'
    CACHE_HISTORICAL = True  # Retrieving a large range, so use a daily cache

    def __init__(self, config: Config):
        super().__init__(config)
        self.PROVIDER_CURRENCY = self.config.main.currency  # CoinGecko supports currency conversion natively
        self.cg = CoinGeckoAPI()

    def symbol_to_id(self):
        symbol = self.config.main.crypto.lower()
        coins = self.cg.get_coins_list()
        for coin in coins:
            if coin['symbol'] == symbol:
                return coin['id']
        raise ValueError(f"Could not map {self.config.main.crypto} to a CoinGecko ID")

    def current(self) -> Point:
        if len(self.config.main.stock):
            raise NotImplementedError("Stock not implemented for CoinGecko Provider")

        crypto = self.symbol_to_id()
        currency = self.config.main.currency.lower()
        price = self.cg.get_price(ids=crypto, vs_currencies=currency)

        return Point(timestamp=datetime.now(), data=self.currency_convert(price[crypto][currency]))

    def historical(self) -> Series:
        if len(self.config.main.stock):
            raise NotImplementedError("Stock not implemented for CoinGecko Provider")

        start = datetime.today() - timedelta(days=100)  # need to use >90 days to get daily granularity
        end = datetime.today() - timedelta(days=1)
        crypto = self.symbol_to_id()
        currency = self.config.main.currency.lower()

        prices = self.cg.get_coin_market_chart_range_by_id(crypto, currency, start.timestamp(), end.timestamp())
        results = []
        for ts, price in prices['prices']:
            day = datetime.fromtimestamp(ts//1000)  # millisecond timestamps
            p = Point(timestamp=day, data=self.currency_convert(price))
            results.append(p)

        return Series(series=results)
