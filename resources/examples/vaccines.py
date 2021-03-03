import logging
import argparse
import requests
from datetime import datetime

from inkystock.config import Config
from inkystock.layout import Container, Layout
from inkystock.paint import Pillow
from inkystock.stocks.base import Series, Point

from vaccines_ui import StatusBar, TickerBar, Headline, Chart


def setup_logging(level: str) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(filename)s:%(module)s:%(funcName)s:%(lineno)d]: %(message)s")
    log = logging.getLogger("inkystock")
    log.setLevel(getattr(logging, level))
    return log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.ini")
    parser.add_argument("--country", required=True)
    args = parser.parse_args()

    config = Config(path=args.config)
    log = setup_logging(config.main.loglevel)

    r = requests.get("https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.json")
    vaccinations = r.json()

    info = {}
    for country in vaccinations:
        if country['country'] == args.country:
            info = country
            break

    # the painter is responsible for turning the layout we're specifying into pixels
    painter = Pillow()

    # The details (elements, layout, etc) of UI components are specified in ui.py.
    # This hopefully makes the relationship between the data and its layout clearer.
    status_bar = StatusBar(config, painter, f"Vaccinations {info['country']}").build()

    # The latest price is pulled and stored with a timestamp on each invocation of the application.
    # Here, it's formatted as a list of floats in reverse order so it can be displayed as a price ticker.
    cleaned = sorted([d for d in info['data'] if 'daily_vaccinations_raw' in d], key=lambda i: i['date'])
    ticks = [d['daily_vaccinations_raw'] for d in cleaned]
    ticker_bar = TickerBar(config, painter, [f"{tick}" for tick in ticks]).build()

    # The most recent price is compared to yesterday's close to determine the price change.
    # That feeds into the arrow orientation, as well as which mascot gets picked to go alongside the price.
    # The most recent price is set as the "headline" price.
    rev = [t for t in reversed(ticks)]
    most_recent = rev[0]
    previous = rev[1]
    log.info(f"Most recent vaccination number {most_recent} (previous: {previous})")

    change = most_recent - previous

    headline = Headline(config, painter, most_recent, change).build()

    hist = [Point(timestamp=datetime.strptime(h['date'], '%Y-%m-%d'), data=h['total_vaccinations']) for h in cleaned]
    historical = Series(series=hist)

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
    # The resulting image is saved locally for optional inspection
    image.render().save(config.outputs.local)

    # The image is then rendered to the display. The InkyPHAT display has an idiosyncratic palette; inverting normal
    # black and white is enough to have it render correctly, and it's more convenient to do at this point, so that the
    # intermediate images can be rendered and viewed normally.
    if config.outputs.screen == "inky":
        painter.display(image)


if '__main__' == __name__:
    main()
