import hashlib
import json
import logging
from datetime import date

from sqlalchemy import Table, Column, Numeric, String, DateTime, MetaData
from sqlalchemy import create_engine, exc
from sqlalchemy.sql import select

from inkystock.config import Config
from inkystock.stocks.base import Point, Series

log = logging.getLogger("inkystock")


class Database:

    def __init__(self, config: Config):
        self.config = config
        self.engine = create_engine(self.config.main.database)

        metadata = MetaData()
        self.prices = Table('prices', metadata,
                            Column('datetime', DateTime),
                            Column('provider', String),
                            Column('currency', String),
                            Column('asset', String),
                            Column('price', Numeric))
        self.cache = Table('cache', metadata,
                           Column('key', String, primary_key=True),
                           Column('value', String))
        metadata.create_all(self.engine)
        self.conn = self.engine.connect()

    def asset(self):
        if len(self.config.main.crypto):
            return self.config.main.crypto
        else:
            return self.config.main.stock

    def cache_key(self):
        m = hashlib.md5()
        m.update(date.today().isoformat().encode('utf-8'))
        m.update(self.config.main.currency.encode('utf-8'))
        m.update(self.asset().encode('utf-8'))
        m.update(self.config.main.provider.encode('utf-8'))
        return m.hexdigest()

    def store_current(self, current: Point) -> Point:

        ins = self.prices.insert().values(datetime=current.timestamp,
                                          currency=self.config.main.currency,
                                          provider=self.config.main.provider,
                                          asset=self.asset(),
                                          price=current.data)
        self.conn.execute(ins)
        return current

    def store_historical(self, historical: Series) -> Series:
        try:
            log.debug(f"Caching historical data with key {self.cache_key()}")
            ins = self.cache.insert().values(key=self.cache_key(), value=historical.json())
            self.conn.execute(ins)
        except exc.IntegrityError as e:
            log.warning(e)
        return historical

    def retrieve_historical(self) -> Series:
        log.debug(f"Retrieving historical data with key {self.cache_key()}")
        s = select([self.cache]) \
            .where(self.cache.c.key == self.cache_key())
        key, result = self.conn.execute(s).first()
        log.debug(f"Historical data: {result}")

        return Series(series=json.loads(result)['series'])

    def recent(self) -> Series:
        s = select([self.prices]) \
            .where(self.prices.c.currency == self.config.main.currency) \
            .where(self.prices.c.asset == self.asset()) \
            .where(self.prices.c.provider == self.config.main.provider) \
            .order_by(self.prices.c.datetime.desc()) \
            .limit(10)
        rs = self.conn.execute(s)
        results = []
        for r in rs:
            p = Point(timestamp=r[0], data=r[4])
            results.append(p)
        return Series(series=results)
