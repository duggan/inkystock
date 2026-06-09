import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Optional

import requests
from pydantic import BaseModel

from inkystock.config import Config

log = logging.getLogger("inkystock")

# Keyless ECB reference rates (https://frankfurter.dev) — replaces forex-python,
# which needs no key either but is flaky and makes a request per conversion.
FOREX_URL = "https://api.frankfurter.dev/v1/latest"
# (connect, read) timeouts shared by all provider HTTP calls so a half-open
# connection can never wedge the device.
HTTP_TIMEOUT = (3.05, 10)


class Point(BaseModel):
    timestamp: datetime
    data: float


class Series(BaseModel):
    series: List[Point]


class Stock(ABC):
    PROVIDER_CURRENCY = 'EUR'
    CACHE_HISTORICAL = False

    def __init__(self, config: Config):
        self.config = config
        self._rate: Optional[float] = None
        self._rate_date: Optional[date] = None

    def currency_convert(self, amount) -> float:
        """Convert amount from PROVIDER_CURRENCY to the configured currency.

        No-op when the provider already prices in the target currency (e.g.
        Coinbase requested as BTC-EUR). Otherwise fetch one ECB rate per day and
        reuse it — cheap for cron and safe for a long-lived daemon.
        """
        target = self.config.main.currency
        if self.PROVIDER_CURRENCY == target:
            return float(amount)
        if self._rate is None or self._rate_date != date.today():
            log.debug(f"Fetching {self.PROVIDER_CURRENCY}->{target} rate from Frankfurter")
            r = requests.get(FOREX_URL,
                             params={"base": self.PROVIDER_CURRENCY, "symbols": target},
                             timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            self._rate = float(r.json()["rates"][target])
            self._rate_date = date.today()
        return float(amount) * self._rate

    @abstractmethod
    def historical(self) -> Series:
        pass

    @abstractmethod
    def current(self) -> Point:
        pass
