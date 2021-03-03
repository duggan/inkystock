import logging

from inkystock.config import Config
from inkystock.paint import Pillow
from inkystock.layout import Container, Layout, Display, Align, Padding, Border


def setup_logging(level: str) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(filename)s:%(module)s:%(funcName)s:%(lineno)d]: %(message)s")
    log = logging.getLogger("inkystock")
    log.setLevel(getattr(logging, level))
    return log


config = Config(path="hello_world.ini")

setup_logging(config.main.loglevel)

painter = Pillow()

root = Container()

hello_world = Container(display=Display.BLOCK,
                        align=Align.LEFT,
                        padding=Padding(top=2, left=2, bottom=2, right=2),
                        border=Border(top=1, left=1, bottom=1, right=1))
hello_world.add(painter.text("Hello, world!",
                             font=config.fonts.statusbar,
                             font_size=config.fonts.statusbar_size))

root.add(hello_world)

layout = Layout(root).layout()

image = painter.paint((hello_world.width(), hello_world.height()), layout)
image.render().save("./hello_world.png")
