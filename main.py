import logging
import argparse

from inkystock.config import Config
from inkystock.db import Database
from inkystock.layout import Container, Layout
from inkystock.paint import Pillow
from inkystock.stocks.coingecko import CoinGecko
from inkystock.stocks.iex import IEX
from inkystock.stocks.mock import Mock

from ui import StatusBar, TickerBar, Headline, Chart


def setup_logging(level: str) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(filename)s:%(module)s:%(funcName)s:%(lineno)d]: %(message)s")
    log = logging.getLogger("inkystock")
    log.setLevel(getattr(logging, level))
    return log


def main():
    # Pull in expected environment variables for replacement in config.ini
    # Need to do this otherwise variable interpolation breaks on the Pi due to some funky stuff in LS_COLORS
    # There may be other weird stuff set, so safer just to use an allow-list.
    env_vars = [
        'IEX_TOKEN',
        'IEX_ENDPOINT',
        'INKYSTOCK_SCREEN',
        'INKYSTOCK_DATABASE',
    ]
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.ini")
    args = parser.parse_args()

    config = Config(env_vars=env_vars, path=args.config)
    log = setup_logging(config.main.loglevel)

    db = Database(config)

    if config.main.provider == 'IEX':
        stocks = IEX(config)
    elif config.main.provider == 'CoinGecko':
        stocks = CoinGecko(config)
    elif config.main.provider == 'MOCK':
        stocks = Mock(config)
    else:
        raise NotImplementedError(f"There is no stock provider available for {config.main.provider}")

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

    # the painter is responsible for turning the layout we're specifying into pixels
    painter = Pillow()

    # The details (elements, layout, etc) of UI components are specified in ui.py.
    # This hopefully makes the relationship between the data and its layout clearer.
    status_bar = StatusBar(config, painter).build()

    # The latest price is pulled and stored with a timestamp on each invocation of the application.
    # Here, it's formatted as a list of floats in reverse order so it can be displayed as a price ticker.
    ticks = [r.data for r in recent.series]
    ticker_bar = TickerBar(config, painter, [f"{tick:.2f}" for tick in reversed(ticks)]).build()

    # The most recent price is compared to yesterday's close to determine the price change.
    # That feeds into the arrow orientation, as well as which mascot gets picked to go alongside the price.
    # The most recent price is set as the "headline" price.
    most_recent = ticks[0]
    yesterday = [h.data for h in reversed(historical.series)][0]
    asset = config.main.crypto if len(config.main.crypto) else config.main.stock
    log.info(f"Most recent price in {config.main.currency} for {asset}: {most_recent} (last close: {yesterday})")

    change = most_recent - yesterday

    headline = Headline(config, painter, current.data, change).build()

    # The chart plots a timeseries. It's difficult to get too much detail at the low resolution of an InkyPHAT, so
    # this is most useful for large trends.
    chart = Chart(config, painter, historical).build()

    # The layout is assembled by combining the containers in order from top to bottom and left to right, depending on
    # the <display> configuration.
    root = Container(name="root")
    root.add(status_bar)
    root.add(ticker_bar)
    root.add(headline)
    root.add(chart)

    # The physical pixel dimensions are calculated in the layout step
    layout = Layout(root).layout()
    # An image object is created based on the layout
    size = (config.main.display_width_pixels, config.main.display_height_pixels)
    image = painter.paint(size, layout)
    # Rotate the image if configured
    if config.main.rotate_display:
        image.rotate(config.main.rotate_display)
    # The resulting image is saved locally for optional inspection
    image.render().save(config.outputs.local)

    # The image is then rendered to the display. The InkyPHAT display has an idiosyncratic palette; inverting normal
    # black and white is enough to have it render correctly, and it's more convenient to do at this point, so that the
    # intermediate images can be rendered and viewed normally.
    if config.outputs.screen == "inky":
        painter.display(image)


if '__main__' == __name__:
    main()
