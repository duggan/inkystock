from math import floor, log10

from PIL import Image, ImageDraw, ImageFont

from inkystock.config import Config
from inkystock.layout import Element
from inkystock.stocks.base import Series
from inkystock.paint import PaletteData, Color


def _nice_ticks(lo: float, hi: float, target: int = 2):
    """Pick ~`target` round tick values spanning [lo, hi].

    A tiny stand-in for matplotlib's MaxNLocator so the y-axis lands on
    human-friendly numbers (e.g. 0, 10000) rather than the raw data range.
    """
    if hi <= lo:
        return [lo]
    raw_step = (hi - lo) / target
    magnitude = 10 ** floor(log10(raw_step))
    for mult in (1, 2, 2.5, 5, 10):
        step = mult * magnitude
        if raw_step <= step:
            break
    ticks = []
    v = floor(lo / step) * step
    while v <= hi + step * 0.001:
        if v >= lo - step * 0.001:
            ticks.append(v)
        v += step
    return ticks or [lo, hi]


class Chart(Element):
    """Render a price sparkline directly with Pillow.

    Previously this used matplotlib, whose import alone costs several seconds on
    a Raspberry Pi Zero, to draw a chart on a 212x104 panel. Drawing it directly
    with Pillow (already a dependency) removes that cost entirely.
    """

    TIMESTAMP_FORMAT = "%-d/%-m"

    TICK_LEN = 2
    GAP = 2
    MARGIN = 0.06  # fraction of plot height kept clear above/below the line

    def __init__(self, config: Config, width: int, height: int):
        self.config = config
        self._width = width
        self._height = height
        self._series = None
        self._cache = None

        # Match the panel palette so the rendered chart pastes straight onto the
        # canvas with no per-element quantization. On colour panels the trend
        # line uses the accent ink (index 2); otherwise it's black.
        if self.config.main.color in ('red', 'yellow'):
            self._palette = PaletteData.COLOR
            self._line = 2
        else:
            self._palette = PaletteData.BLACK_AND_WHITE
            self._line = Color.BLACK

        self._font = ImageFont.truetype(self.config.fonts.chart,
                                        max(5, int(round(self.config.fonts.chart_size))))

    def __repr__(self):
        return f"(Chart size={self.size()})"

    def size(self):
        return self._width, self._height

    def plot(self, s: Series):
        self._series = s
        self._cache = None

    def _format_y(self, value: float, ymax: float) -> str:
        if ymax > 999:
            # 'K' to denominate thousands so labels stay narrow
            return f"{int(value / 1000)}K"
        if ymax < 1:
            # two decimals, leading zero stripped, when prices are sub-1
            return f"{value:.2f}".lstrip('0')
        return f"{value:g}"

    def render(self):
        if self._cache:
            return self._cache

        image = Image.new('P', (self._width, self._height), Color.WHITE)
        image.putpalette(self._palette)
        draw = ImageDraw.Draw(image)

        points = self._series.series
        values = [p.data for p in points]
        labels = [p.timestamp.strftime(self.TIMESTAMP_FORMAT) for p in points]
        ymin, ymax = min(values), max(values)
        span = (ymax - ymin) or 1

        # Pick ticks across the padded (visible) range, so a clean bound such as
        # 0 just outside the data range still gets a label, as matplotlib did.
        pad = self.MARGIN * span
        ticks = _nice_ticks(ymin - pad, ymax + pad)
        label_h = self._font.getbbox("0/0")[3]
        y_label_w = max(int(draw.textlength(self._format_y(t, ymax), font=self._font)) for t in ticks)

        left = y_label_w + self.GAP + self.TICK_LEN
        right = self._width - 1
        top = 1
        baseline = self._height - label_h - self.GAP
        plot_w = right - left
        plot_h = baseline - top

        # Axes ("spines"): left and bottom only, matching the previous look.
        draw.line([(left, top), (left, baseline)], fill=Color.BLACK)
        draw.line([(left, baseline), (right, baseline)], fill=Color.BLACK)

        def to_y(value: float) -> int:
            frac = self.MARGIN + (value - ymin) / span * (1 - 2 * self.MARGIN)
            return int(baseline - frac * plot_h)

        def to_x(index: int) -> int:
            if len(values) == 1:
                return left + plot_w // 2
            return int(left + index / (len(values) - 1) * plot_w)

        # Y ticks + labels
        for tick in ticks:
            ty = to_y(tick)
            draw.line([(left - self.TICK_LEN, ty), (left, ty)], fill=Color.BLACK)
            text = self._format_y(tick, ymax)
            tw = draw.textlength(text, font=self._font)
            draw.text((left - self.TICK_LEN - self.GAP - tw, ty - label_h / 2),
                      text, fill=Color.BLACK, font=self._font)

        # X labels, one per point, centred and clamped to the canvas
        for index, text in enumerate(labels):
            tw = draw.textlength(text, font=self._font)
            tx = min(max(0, to_x(index) - tw / 2), self._width - tw)
            draw.text((tx, baseline + self.GAP), text, fill=Color.BLACK, font=self._font)

        # The price line itself
        line = [(to_x(i), to_y(v)) for i, v in enumerate(values)]
        draw.line(line, fill=self._line, width=1)

        self._cache = image
        return self._cache
