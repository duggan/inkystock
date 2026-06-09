import logging
import argparse
import os
import socket
import time

from inkystock.config import Config
from inkystock.db import Database
from inkystock.layout import Container, Layout
from inkystock.paint import Pillow
from inkystock.stocks.coinbase import Coinbase
from inkystock.stocks.coingecko import CoinGecko
from inkystock.stocks.mock import Mock
from inkystock.stocks.yahoo import Yahoo

from ui import StatusBar, TickerBar, Headline, Chart


def setup_logging(level: str) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(filename)s:%(module)s:%(funcName)s:%(lineno)d]: %(message)s")
    log = logging.getLogger("inkystock")
    log.setLevel(getattr(logging, level))
    return log


def sd_notify(state: str) -> None:
    """Best-effort systemd notification. A no-op unless launched by systemd with
    Type=notify (i.e. when $NOTIFY_SOCKET is set), so it's harmless under cron or
    a manual run."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):  # abstract namespace socket
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(addr)
            sock.sendall(state.encode())
    except OSError:
        pass


def sleep_with_watchdog(seconds: int, ping: int = 45) -> None:
    """Sleep, pinging the systemd watchdog periodically so an idle daemon stays
    alive while a genuinely wedged update (which never pings) gets killed."""
    remaining = seconds
    while remaining > 0:
        nap = min(ping, remaining)
        time.sleep(nap)
        remaining -= nap
        sd_notify("WATCHDOG=1")


def make_provider(config: Config):
    provider = config.main.provider
    if provider == 'Coinbase':
        return Coinbase(config)
    elif provider == 'Yahoo':
        return Yahoo(config)
    elif provider == 'CoinGecko':
        return CoinGecko(config)
    elif provider == 'MOCK':
        return Mock(config)
    raise NotImplementedError(f"There is no stock provider available for {provider}")


def update(config: Config, db: Database, stocks, painter: Pillow, log: logging.Logger) -> None:
    """Fetch the latest data and render one frame to the configured output(s)."""
    # The latest price is pulled and stored with a timestamp on each update.
    log.info("Pulling current data from API and caching")
    current = db.store_current(stocks.current())

    if stocks.CACHE_HISTORICAL:
        log.info("Pulling historical data from API and caching")
        try:
            historical = db.retrieve_historical()
        except Exception as e:
            log.warning(e)
            historical = db.store_historical(stocks.historical())
    else:
        log.info("Pulling historical data from API")
        historical = stocks.historical()

    recent = db.recent()

    # The details (elements, layout, etc) of UI components are specified in ui.py.
    status_bar = StatusBar(config, painter).build()

    # Recent prices, formatted as a reverse-order ticker.
    ticks = [r.data for r in recent.series]
    ticker_bar = TickerBar(config, painter, [f"{tick:.2f}" for tick in reversed(ticks)]).build()

    # The most recent price is compared to yesterday's close to determine the
    # price change, which drives the arrow orientation and mascot.
    most_recent = ticks[0]
    yesterday = [h.data for h in reversed(historical.series)][0]
    asset = config.main.crypto if len(config.main.crypto) else config.main.stock
    log.info(f"Most recent price in {config.main.currency} for {asset}: {most_recent} (last close: {yesterday})")

    change = most_recent - yesterday

    headline = Headline(config, painter, current.data, change).build()

    # Size the chart to the height left over below the bars and headline, so its
    # x-axis date labels are never clipped by the bottom edge of the panel.
    used_height = status_bar.height() + ticker_bar.height() + headline.height()
    chart = Chart(config, painter, historical,
                  height=config.main.display_height_pixels - used_height).build()

    # Assemble the layout from top to bottom.
    root = Container(name="root")
    root.add(status_bar)
    root.add(ticker_bar)
    root.add(headline)
    root.add(chart)

    layout = Layout(root).layout()
    size = (config.main.display_width_pixels, config.main.display_height_pixels)
    image = painter.paint(size, layout)
    if config.main.rotate_display:
        image.rotate(config.main.rotate_display)
    # Save a local snapshot for optional inspection.
    image.render().save(config.outputs.local)

    # Then render to the physical display if configured.
    if config.outputs.screen == "inky":
        painter.display(image)


def main():
    # Pull in expected environment variables for replacement in config.ini.
    # Need an allow-list otherwise variable interpolation breaks on the Pi due to
    # funky values in things like LS_COLORS.
    env_vars = [
        'INKYSTOCK_SCREEN',
        'INKYSTOCK_DATABASE',
    ]
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.ini")
    parser.add_argument("--daemon", action="store_true",
                        help="run continuously, updating every --interval seconds "
                             "(default: perform a single update and exit)")
    parser.add_argument("--interval", type=int, default=300,
                        help="seconds between updates in --daemon mode (default: 300)")
    args = parser.parse_args()

    config = Config(env_vars=env_vars, path=args.config)

    log = setup_logging(config.main.loglevel)

    log.info(f"Configured resolution: {config.main.display_width_pixels}x{config.main.display_height_pixels}")
    log.info(f"Configured color: {config.main.color}")

    # Built once and reused across updates — this is what makes the daemon cheap:
    # the interpreter, imports and hardware probe are paid for a single time.
    db = Database(config)
    stocks = make_provider(config)
    painter = Pillow(config)

    if not args.daemon:
        update(config, db, stocks, painter, log)
        return

    log.info(f"Starting InkyStock daemon; updating every {args.interval}s")
    sd_notify("READY=1")
    while True:
        try:
            update(config, db, stocks, painter, log)
            sd_notify("WATCHDOG=1")
        except Exception:
            # A transient API/network error should skip this tick, not kill the
            # daemon — the next interval will try again.
            log.exception("Update failed; will retry next interval")
        sleep_with_watchdog(args.interval)


if '__main__' == __name__:
    main()
