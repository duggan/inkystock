"""
This whole module is an exercise in understanding the application flow.
It's not strictly necessary since I don't expect to be using anything other than Pillow,
but it helps keep parts of the system to do with "painting" separate from the layout engine.
"""
import abc
import logging
from typing import Sequence, Tuple

# I want to use the Image name myself, renaming the others for consistency
from PIL import ImageFont as PILFont, Image as PILImage, ImageDraw as PILDraw
from inky.auto import auto

from inkystock import Element
from inkystock.layout import LayoutList, Container, Layout, Border

log = logging.getLogger("inkystock")


class Color:
    BLACK = 0
    WHITE = 1


class Image(Element):

    @abc.abstractmethod
    def open(self, fp):
        pass

    @abc.abstractmethod
    def save(self, fp, fmt=None):
        pass

    @abc.abstractmethod
    def rotate(self, degrees):
        pass

    @abc.abstractmethod
    def invert(self):
        pass

    @abc.abstractmethod
    def border(self, border: Border):
        pass

    @abc.abstractmethod
    def render(self):
        pass


class PillowImage(Image):

    def __init__(self, im: PILImage):
        self.image = im

    def __repr__(self):
        return f"(PillowImage size={self.size()})"

    def size(self) -> Tuple[int, int]:
        return self.image.size

    def open(self, fp):
        self.image.open(fp)
        return self

    def save(self, fp, fmt=None):
        self.image.save(fp, format=fmt)
        return self

    def rotate(self, degrees):
        log.debug(f"Rotating image {degrees} degrees")
        self.image = self.image.rotate(degrees)
        return self

    def invert(self):
        log.debug("Inverting image colours")
        inverted = PILImage.new('1', self.image.size)
        remapped = []
        pxmap = {0: 2, 1: 0, 2: 0, 255: 0}
        for px in self.image.getdata():
            remapped.append(pxmap[px])
        inverted.putdata(remapped)
        self.image = inverted
        return self

    def border(self, border: Border):
        if border == Border():
            return self
        log.debug(f"Drawing {border}")

        draw = PILDraw.Draw(self.image)
        width, height = self.size()

        if border.left:
            draw.line([(0, 0), (0, width)], fill=Color.BLACK, width=border.left)
        if border.right:
            draw.line([(width - border.right, 0), (width - border.right, height)], fill=Color.BLACK,
                      width=border.right)
        if border.top:
            draw.line([(0, 0), (width, 0)], fill=Color.BLACK, width=border.top)
        if border.bottom:
            draw.line([(0, height - border.bottom), (width, height - border.bottom)], fill=Color.BLACK,
                      width=border.bottom)
        return self

    def render(self) -> PILImage.Image:
        # FIXME: this should return a bytearray or something else generic
        return self.image


class Text(Element):

    def __init__(self, image: Image, text: str, font: str, font_size: int):
        self.image = image
        self.text = text
        self.font = font
        self.font_size = font_size

    def render(self):
        return self.image.render()

    def size(self):
        return self.image.size()

    def __repr__(self):
        return f"Text(image_size={self.image.size()}, text={self.text}, font={self.font}, font_size={self.font_size})"


class Painter(abc.ABC):

    @abc.abstractmethod
    def new(self, size: Tuple[int, int]):
        pass

    @abc.abstractmethod
    def from_file(self, path):
        pass

    @abc.abstractmethod
    def text(self, text, font: str, font_size: int) -> Text:
        pass

    @abc.abstractmethod
    def line(self, size: Tuple[int, int]):
        pass

    @abc.abstractmethod
    def triangle(self, size: Tuple[int, int], rotate: int = 0):
        pass

    @abc.abstractmethod
    def polygon(self, size: Tuple[int, int], points: Sequence) -> Image:
        pass

    @abc.abstractmethod
    def display(self, image: Image):
        pass

    @abc.abstractmethod
    def paint(self, size: Tuple[int, int], layout: LayoutList):
        pass


class Pillow(Painter):

    def new(self, size: Tuple[int, int]):
        return PillowImage(PILImage.new('1', size, Color.WHITE))

    def from_file(self, path):
        return PillowImage(PILImage.open(path))

    def text(self, text, font: str, font_size: int) -> Text:
        """
        Draw text to an image and return.
        :param text:
        :param font:
        :param font_size:
        :return: Image
        """
        # Initialize the font
        ttf = PILFont.truetype(font, int(font_size))

        # Get the dimensions of the font that *would* be rendered, then create a temporary canvas
        # with those dimensions to draw on.
        bbox = ttf.getbbox(text)
        width = bbox[2] - bbox[0]
        height = bbox[3]  # have to ignore bbox[1] because it produces cropped text
        size = (width, height)
        log.debug(f"Bounding box for {text}: {bbox}, size: {size}")
        canvas = PILImage.new('1', size, Color.WHITE)
        draw = PILDraw.Draw(canvas)

        # Draw the text to the temporary canvas.
        draw.text((0, 0), text, Color.BLACK, font=ttf)

        return Text(image=PillowImage(canvas), text=text, font=font, font_size=font_size)

    def triangle(self, size: Tuple[int, int], rotate: int = 0) -> Image:
        width = size[0]
        height = size[1]

        apex = (int(width / 2), 0)
        left = (0, height)
        right = (width, height)
        points = [apex, left, right]

        poly = self.polygon(size, points)
        return poly.rotate(rotate)

    def line(self, size: Tuple[int, int]):
        canvas = PILImage.new('1', size, Color.WHITE)
        draw = PILDraw.Draw(canvas)
        draw.line([(0, 0), (size[0], 0)], fill=Color.BLACK, width=size[1])
        return PillowImage(canvas)

    def polygon(self, size: Tuple[int, int], points: Sequence) -> Image:
        canvas = PILImage.new('1', size, Color.WHITE)
        draw = PILDraw.Draw(canvas)

        draw.polygon(points, fill=Color.BLACK)
        return PillowImage(canvas)

    def display(self, image: PillowImage):
        board = auto()
        board.set_image(image.invert().render())
        board.show()

    def paint(self, size: Tuple[int, int], layout: LayoutList):
        canvas = self.new(size).render()
        for position, element in layout:
            if type(element) is Container:
                content = self.paint(element.size(), Layout(element).layout())
                bordered = PillowImage(content.render()).border(element.border)
                canvas.paste(bordered.render(), (position.x, position.y))
            else:
                image = element.render()
                log.info(f"Rendering {element} to canvas, size: {image.size} position: {position}")
                # Use alpha blending where applicable (e.g., mascots)
                mask = image if image.mode != '1' else None
                canvas.paste(image, (position.x, position.y), mask=mask)
        return PillowImage(canvas)
