import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from forex_python.converter import CurrencyRates
from pydantic import BaseModel

from inkystock.config import Config


log = logging.getLogger("inkystock")


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
        self.currency = CurrencyRates()

    def currency_convert(self, amount) -> float:
        if self.PROVIDER_CURRENCY == self.config.main.currency:
            return float(amount)
        log.debug(f"Converting {amount} {self.PROVIDER_CURRENCY} to {self.config.main.currency}")
        return self.currency.convert(self.PROVIDER_CURRENCY, self.config.main.currency, float(amount))

    @abstractmethod
    def historical(self) -> Series:
        pass

    @abstractmethod
    def current(self) -> Point:
        pass
