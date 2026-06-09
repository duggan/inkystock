import hashlib
import json
import logging
import sqlite3
from datetime import date

from inkystock.config import Config
from inkystock.stocks.base import Point, Series

log = logging.getLogger("inkystock")


def sqlite_path(database: str) -> str:
    """Turn a SQLAlchemy-style sqlite URL into a path for stdlib sqlite3.

    Kept for backward compatibility with existing config.ini files:
      sqlite:///relative/file.db  -> relative/file.db   (3 slashes = relative)
      sqlite:////absolute/file.db -> /absolute/file.db  (4 slashes = absolute)
      sqlite://  /  sqlite:///:memory: -> :memory:
    A plain path (no scheme) is returned untouched.
    """
    if not database.startswith("sqlite:"):
        return database
    remainder = database[len("sqlite://"):]
    # Strip exactly one leading slash: the relative form keeps none, the
    # absolute form keeps its leading slash.
    if remainder.startswith("/"):
        remainder = remainder[1:]
    return remainder or ":memory:"


class Database:

    def __init__(self, config: Config):
        self.config = config
        self.conn = sqlite3.connect(sqlite_path(self.config.main.database))
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS prices ("
            "datetime TIMESTAMP, provider TEXT, currency TEXT, asset TEXT, price REAL)")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()

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
        self.conn.execute(
            "INSERT INTO prices (datetime, provider, currency, asset, price) "
            "VALUES (?, ?, ?, ?, ?)",
            (current.timestamp.isoformat(), self.config.main.provider,
             self.config.main.currency, self.asset(), float(current.data)))
        self.conn.commit()
        return current

    def store_historical(self, historical: Series) -> Series:
        try:
            log.debug(f"Caching historical data with key {self.cache_key()}")
            self.conn.execute("INSERT INTO cache (key, value) VALUES (?, ?)",
                              (self.cache_key(), historical.json()))
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            log.warning(e)
        return historical

    def retrieve_historical(self) -> Series:
        log.debug(f"Retrieving historical data with key {self.cache_key()}")
        row = self.conn.execute("SELECT value FROM cache WHERE key = ?",
                                (self.cache_key(),)).fetchone()
        if row is None:
            raise KeyError(f"No cached historical data for key {self.cache_key()}")
        result = row[0]
        log.debug(f"Historical data: {result}")
        return Series(series=json.loads(result)['series'])

    def recent(self) -> Series:
        rows = self.conn.execute(
            "SELECT * FROM prices "
            "WHERE currency = ? AND asset = ? AND provider = ? "
            "ORDER BY datetime DESC LIMIT 10",
            (self.config.main.currency, self.asset(), self.config.main.provider)).fetchall()
        # Column order matches the CREATE TABLE above: datetime is r[0], price is r[4].
        return Series(series=[Point(timestamp=r[0], data=r[4]) for r in rows])
