from abc import ABC, abstractmethod
from datetime import datetime
from typing import Tuple

from inkystock.chart import Chart as ChartBuilder
from inkystock.config import Config
from inkystock.layout import Container, Padding, Align, Display, Border
from inkystock.paint import Painter
from inkystock.stocks.base import Series


class Orientation:
    """
    Shorthand for degrees on the circle used in rotating images (e.g., arrows).
    """
    UP = 0
    DOWN = 180
    LEFT = 90
    RIGHT = 270


class UI(ABC):

    def __init__(self, config: Config, painter: Painter):
        self.config = config
        self.painter = painter

    def paint_arrow(self, size: Tuple[int, int], orientation: int):
        return self.painter.triangle(size, orientation)

    @abstractmethod
    def build(self) -> Container:
        pass


class StatusBar(UI):
    FORMAT_DATETIME = "%-d/%-m  %H:%M"

    def paint_text(self, text):
        return self.painter.text(text=text,
                                 font=self.config.fonts.statusbar,
                                 font_size=self.config.fonts.statusbar_size)

    def paint_symbol(self, text):
        return self.painter.text(text=text,
                                 font=self.config.fonts.symbol,
                                 font_size=self.config.fonts.symbol_size)

    def build(self) -> Container:
        # Status Bar Boxes
        status_bar_left = Container(width=int(self.config.main.display_width_pixels / 2),
                                    display=Display.INLINE,
                                    padding=Padding(bottom=1),
                                    name="status_bar_left")

        # Stock symbol and currency conversion information
        asset = self.config.main.crypto if len(self.config.main.crypto) else self.config.main.stock
        status_bar_left.add(self.paint_text(asset))
        status_bar_left.add(self.paint_symbol("w"))
        status_bar_left.add(self.paint_text(self.config.main.currency))

        # Date and time

        status_bar_right = Container(int(self.config.main.display_width_pixels / 2),
                                     align=Align.RIGHT,
                                     display=Display.INLINE,
                                     padding=Padding(right=1),
                                     name="status_bar_right")

        date_text = self.painter.text(text=datetime.now().strftime(self.FORMAT_DATETIME),
                                      font=self.config.fonts.statusbar,
                                      font_size=self.config.fonts.statusbar_size)
        status_bar_right.add(date_text)

        status_bar = Container(width=self.config.main.display_width_pixels,
                               display=Display.INLINE,
                               padding=Padding(top=1, bottom=1),
                               name="status_bar")

        # Insert left and right into Status Bar
        status_bar.add(status_bar_left)
        status_bar.add(status_bar_right)
        return status_bar


class TickerBar(UI):

    def __init__(self, config: Config, painter: Painter, ticks: list):
        super().__init__(config, painter)
        self.ticks = ticks

    def paint_text(self, text):
        return self.painter.text(text,
                                 font=self.config.fonts.ticker,
                                 font_size=self.config.fonts.ticker_size)

    def build(self) -> Container:
        ticker_bar_text = Container(width=self.config.main.display_width_pixels,
                                    align=Align.RIGHT,
                                    padding=Padding(top=1, bottom=1),
                                    name="ticker_bar_text")

        text = self.paint_text("> " + " > ".join([str(tick) for tick in self.ticks]))
        ticker_bar_text.add(text)

        ticker_bar = Container(self.config.main.display_width_pixels,
                               display=Display.BLOCK,
                               border=Border(top=1, bottom=1),
                               padding=Padding(top=1, bottom=1),
                               align=Align.RIGHT,
                               name="ticker_bar")

        ticker_bar.add(ticker_bar_text)

        return ticker_bar


class Headline(UI):

    def __init__(self, config: Config, painter: Painter, price: float, change: float):
        super().__init__(config, painter)

        self.price = price
        self.change = change

    def paint_image(self, path):
        return self.painter.from_file(path)

    def paint_headline(self, text):
        return self.painter.text(text,
                                 font=self.config.fonts.headline,
                                 font_size=self.config.fonts.headline_size)

    def paint_movement(self, text):
        return self.painter.text(text,
                                 font=self.config.fonts.ticker,
                                 font_size=self.config.fonts.ticker_size)

    def build(self) -> Container:
        # Headline

        orientation = Orientation.DOWN
        mascot_image = self.paint_image(self.config.mascot.static)
        if self.change > 0:
            orientation = Orientation.UP
            mascot_image = self.paint_image(self.config.mascot.increasing)
        elif self.change < 0:
            mascot_image = self.paint_image(self.config.mascot.decreasing)

        arrow = self.paint_arrow((20, 10), orientation)

        change = f"{self.change:+.2f}"
        if self.change > 999:
            change = f"{int(self.change):+}"
        movement_text = self.paint_movement(change)
        movement = Container(display=Display.BLOCK, name="movement")
        spacer = Container(height=2, name="spacer")

        if self.change > 0:
            movement.add(arrow)
            movement.add(spacer)
            movement.add(movement_text)
        else:
            movement.add(movement_text)
            movement.add(spacer)
            movement.add(arrow)

        # Include decimal places for price unless it's over 999
        price = f"{self.price:.2f}"
        if self.price > 999:
            price = f"{int(self.price):,d}"
        price_text = self.paint_headline(price)

        headline_left = Container(width=self.config.main.display_width_pixels - 30,
                                  display=Display.INLINE,
                                  name="headline")
        headline_left.add(price_text)
        headline_left.add(movement)

        headline_right = Container(width=25,
                                   align=Align.RIGHT)
        headline_right.add(mascot_image)

        headline = Container(display=Display.INLINE,
                             padding=Padding(right=2))
        headline.add(headline_left)
        headline.add(headline_right)

        return headline


class Chart(UI):

    def __init__(self, config: Config, painter: Painter, series: Series, limit: int = 7):
        super().__init__(config, painter)

        if limit < 1:
            raise ValueError("limit must be a positive integer")

        self.series = Series(series=series.series[-limit:])

    def build(self) -> Container:
        # Chart
        chart = ChartBuilder(self.config,
                             width=self.config.main.display_width_pixels,
                             height=int(self.config.main.display_height_pixels / 2))
        chart.plot(self.series)

        chart_box = Container(chart.width(),
                              chart.height(),
                              padding=Padding(top=1, left=1, bottom=1),
                              name="chart")
        chart_box.add(chart)
        return chart_box
