import io
from math import sqrt

import matplotlib.pyplot as plt
from PIL import Image
from matplotlib import font_manager, ticker

from inkystock.config import Config
from inkystock.layout import Element
from inkystock.stocks.base import Series
from inkystock.paint import Palette


class Chart(Element):

    TIMESTAMP_FORMAT = "%-d/%-m"

    def __init__(self, config: Config, width: int, height: int):
        # Create Matplotlib pixel chart
        self.config = config
        self._cache = None

        # Trying to approximate appropriate pixel values for feeding to figsize.
        # I haven't gone spelunking through pyplot, so it's just firing numbers into a magic box.
        px = 1.2 / self.dpi()

        # Dock some pixels for the labels (approx, will be affected by font size)
        if self.config.main.display_width_pixels > 212:
            w_offset = 20
        else:
            w_offset = 10
        if self.config.main.display_height_pixels > 104:
            h_offset = 5
        else:
            h_offset = 10
        w = width - w_offset
        h = height - h_offset
        self.fig, self.ax = plt.subplots(figsize=(w*px, h*px))

        # Configure font
        ticks_font = font_manager.FontProperties(fname=self.config.fonts.chart, size=self.config.fonts.chart_size)
        plt.rcParams['text.antialiased'] = False
        for label in self.ax.get_yticklabels():
            label.set_fontproperties(ticks_font)
        for label in self.ax.get_xticklabels():
            label.set_fontproperties(ticks_font)

        # Set padding on axes to a low value
        self.ax.yaxis.set_tick_params(pad=1, width=1)
        self.ax.xaxis.set_tick_params(pad=1, width=1)

        # Remove the right and top borders - "spines" - from the graph
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['top'].set_visible(False)

    def __repr__(self):
        return f"(Chart size={self.size()}, dpi={self.dpi()})"

    def dpi(self) -> float:
        """
        Calculate the DPI based on the display width/height and diagonal inches
        :return:
        """
        diagonal_resolution_px = sqrt(pow(self.config.main.display_width_pixels, 2) +
                                      pow(self.config.main.display_height_pixels, 2))
        return float(int(diagonal_resolution_px / self.config.main.display_diagonal_inches))

    def size(self):
        return self.render().size

    def plot(self, s: Series):
        self._cache = None
        x = []
        y = []
        if max(p.data for p in s.series) > 999:
            # Use 'K' to denominate thousands to stop the labels getting too large
            self.ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v / 1000)}K"))
        elif max(p.data for p in s.series) < 1:
            # Two decimal places and strip leading zeros when price is less than 1
            self.ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.2f}".lstrip('0')))

        for p in s.series:
            x.append(p.timestamp.strftime(self.TIMESTAMP_FORMAT))
            y.append(p.data)
        self.ax.plot(x, y,
                     linewidth=1,
                     linestyle='solid',
                     solid_joinstyle='miter',
                     color=self.config.main.color)

    def render(self):
        if self._cache:
            return self._cache

        if self.config.main.color in ['red', 'yellow']:
            palette = Palette.color()
        else:
            palette = Palette.black_and_white()

        with io.BytesIO() as f:
            self.fig.savefig(f, dpi=self.dpi(), pad_inches=0, bbox_inches='tight')
            chart = Image.open(f).convert('RGB')
            self._cache = chart.quantize(palette=palette)
            return self._cache
