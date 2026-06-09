import logging
from datetime import datetime

import requests

from inkystock.config import Config
from inkystock.stocks.base import Stock, Point, Series, HTTP_TIMEOUT

log = logging.getLogger("inkystock")


class Yahoo(Stock):
    """Keyless stock data from Yahoo Finance's public chart endpoint.

    No API key is required. This is an unofficial endpoint (best-effort): it can
    rate-limit and is not covered by a stable API contract. Prices come in the
    instrument's native currency, converted to the configured currency via the
    base class (Frankfurter / ECB rates).
    """

    CACHE_HISTORICAL = True  # daily closes; cache once per day

    CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    # Yahoo rejects requests without a browser-like User-Agent.
    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; inkystock)"}

    def _fetch(self, range_: str) -> dict:
        if len(self.config.main.crypto):
            raise NotImplementedError("Crypto is not available from the Yahoo provider")
        r = requests.get(self.CHART_URL.format(symbol=self.config.main.stock),
                         params={"range": range_, "interval": "1d"},
                         headers=self.HEADERS, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        # Native currency of the instrument drives the conversion in the base class.
        self.PROVIDER_CURRENCY = result["meta"].get("currency", "USD")
        return result

    def current(self) -> Point:
        result = self._fetch(range_="5d")
        price = result["meta"].get("regularMarketPrice")
        if price is None:
            closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
            price = closes[-1]
        return Point(timestamp=datetime.now(), data=self.currency_convert(price))

    def historical(self) -> Series:
        result = self._fetch(range_="3mo")
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        results = []
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            results.append(Point(timestamp=datetime.fromtimestamp(ts),
                                 data=self.currency_convert(close)))
        return Series(series=results)
