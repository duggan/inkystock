import logging
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from pycoingecko import CoinGeckoAPI
from inkystock.config import Config
from inkystock.stocks.base import Stock, Point, Series


log = logging.getLogger("inkystock")


class CustomCoinGeckoAPI(CoinGeckoAPI):
    def __init__(self, demo_api_key: str = '', retries=5):
        super().__init__(api_key='', retries=retries)  # Call the superclass initializer
        self.demo_api_key = demo_api_key
        if demo_api_key:
            self.session.headers.update({'x_cg_demo_api_key': demo_api_key})

    def __api_url_params(self, api_url, params, api_url_has_params=False):
        # If using a demo version of CoinGecko, inject key in every call
        if self.demo_api_key:
            params['x_cg_demo_api_key'] = self.demo_api_key
        else:
            # If not using demo key, fall back to the original behavior
            if self.api_key:
                params['x_cg_pro_api_key'] = self.api_key

        if params:
            api_url += '&' if api_url_has_params else '?'
            for key, value in params.items():
                if isinstance(value, bool):
                    value = str(value).lower()
                api_url += f"{key}={value}&"
            api_url = api_url[:-1]
        return api_url


class CoinGecko(Stock):
    PROVIDER_CURRENCY = 'USD'
    CACHE_HISTORICAL = True  # Retrieving a large range, so use a daily cache

    def __init__(self, config: Config):
        super().__init__(config)
        self.PROVIDER_CURRENCY = self.config.main.currency  # CoinGecko supports currency conversion natively
        self.cg = CustomCoinGeckoAPI(demo_api_key=config.coingecko.api_key)

    def symbol_to_id(self):
        symbol = self.config.main.crypto.lower()
        if symbol == 'btc':
            return 'bitcoin'
        coins = self.cg.get_coins_list()
        for coin in coins:
            if coin['symbol'] == symbol:
                log.info(f"Mapped crypto sumbol {self.config.main.crypto} to CoinGecko ID {coin['id']}")
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
