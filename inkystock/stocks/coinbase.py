import logging
from datetime import datetime

import requests

from inkystock.config import Config
from inkystock.stocks.base import Stock, Point, Series, HTTP_TIMEOUT

log = logging.getLogger("inkystock")


class Coinbase(Stock):
    """Keyless cryptocurrency data from Coinbase's public API.

    No API key or account is required. Prices are requested directly in the
    configured fiat currency (e.g. BTC-EUR), so no currency conversion is needed.
    """

    CACHE_HISTORICAL = True  # daily candles; cache once per day

    SPOT_URL = "https://api.coinbase.com/v2/prices/{pair}/spot"
    CANDLES_URL = "https://api.exchange.coinbase.com/products/{pair}/candles"

    def __init__(self, config: Config):
        super().__init__(config)
        # Coinbase returns the price already in the target fiat, so conversion in
        # the base class is a no-op.
        self.PROVIDER_CURRENCY = self.config.main.currency
        self.pair = f"{self.config.main.crypto.upper()}-{self.config.main.currency.upper()}"

    def current(self) -> Point:
        if len(self.config.main.stock):
            raise NotImplementedError("Stocks are not available from the Coinbase provider")
        r = requests.get(self.SPOT_URL.format(pair=self.pair), timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        amount = r.json()["data"]["amount"]
        return Point(timestamp=datetime.now(), data=self.currency_convert(amount))

    def historical(self) -> Series:
        if len(self.config.main.stock):
            raise NotImplementedError("Stocks are not available from the Coinbase provider")
        r = requests.get(self.CANDLES_URL.format(pair=self.pair),
                         params={"granularity": 86400}, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        # Candles come back newest-first as [time, low, high, open, close, volume].
        candles = sorted(r.json(), key=lambda c: c[0])
        results = [Point(timestamp=datetime.fromtimestamp(c[0]),
                         data=self.currency_convert(c[4])) for c in candles]
        return Series(series=results)
