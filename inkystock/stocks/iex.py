import logging
from datetime import datetime
from typing import Dict, Union

import requests

from inkystock.config import Config
from inkystock.stocks.base import Stock, Point, Series


log = logging.getLogger("inkystock")


class IEX(Stock):
    PROVIDER_CURRENCY = 'USD'
    CACHE_HISTORICAL = True  # retrieving historical data for IEX uses a lot of credits, so only use it once per day

    def __init__(self, config: Config):
        super().__init__(config)
        log.debug(f"IEX Endpoint: {config.iex.endpoint}")

    def current(self) -> Point:
        if len(self.config.main.crypto):
            raise NotImplementedError("Crypto not implemented for IEX Provider")

        params: Dict[str, str] = {'token': self.config.iex.token}
        r = requests.get(f"{self.config.iex.endpoint}/stock/{self.config.main.stock}/quote/latestPrice", params=params)
        return Point(timestamp=datetime.now(), data=self.currency_convert(r.text))

    def historical(self) -> Series:
        if len(self.config.main.crypto):
            raise NotImplementedError("Crypto not implemented for IEX Provider")

        params: Dict[str, Union[str, bool]] = {'token': self.config.iex.token, 'chartCloseOnly': True}
        r = requests.get(f"{self.config.iex.endpoint}/stock/{self.config.main.stock}/chart/1m", params=params)
        results = []
        for day in r.json():
            p = Point(timestamp=datetime.strptime(day['date'], '%Y-%m-%d'), data=self.currency_convert(day['close']))
            results.append(p)

        return Series(series=results)
