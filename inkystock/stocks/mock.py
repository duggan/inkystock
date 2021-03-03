import random
from datetime import datetime, timedelta

from inkystock.config import Config
from inkystock.stocks.base import Stock, Point, Series


class Mock(Stock):

    def __init__(self, config: Config, days=7):
        super().__init__(config)
        self.prices = Mock.series(100, days + 1)

        dates = []
        for d in range(days):
            dates.append(datetime.today() - timedelta(days=d))
        self.dates = reversed(dates)

    @staticmethod
    def series(x, m):
        exps = []
        for n in range(1, m):
            x = x * 2
            exps.append(float(x))
        return exps

    def historical(self) -> Series:
        prices = []
        for dt, pr in list(zip(self.dates, self.prices)):
            prices.append(Point(timestamp=dt, data=pr))
        return Series(series=prices)

    def current(self) -> Point:
        recent = self.prices[-1]
        jiggle = recent + random.randint(-10, 10)
        return Point(data=jiggle, timestamp=datetime.now())
