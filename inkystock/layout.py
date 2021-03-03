import logging
from copy import copy
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Tuple, Any, Optional

from pydantic import BaseModel, validator

from inkystock import Element

log = logging.getLogger("inkystock")


class Align(Enum):
    LEFT = auto()
    RIGHT = auto()


class Display(Enum):
    BLOCK = auto()
    INLINE = auto()


@dataclass
class Position:
    x: int = 0
    y: int = 0

    def coords(self):
        return self.x, self.y


LayoutList = List[Tuple[Position, Any]]


class BoxModification(BaseModel):
    """
    Base class for setting modifications on containers
    """
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0

    @validator("left", "right", "top", "bottom")
    def non_negative(cls, v):
        assert v >= 0, "Padding may not be negative"
        return v


class Padding(BoxModification):
    """
    Padding for container content
    """


class Border(BoxModification):
    """
    Border of container
    """


class Container(Element):
    """
    Virtual structure for positioning elements on canvas.
    """

    def __init__(self,
                 width: int = 0,
                 height: int = 0,
                 padding: Padding = Padding(),
                 border: Border = Border(),
                 display: Display = Display.BLOCK,
                 align: Align = Align.LEFT,
                 name: str = "anonymous"):
        self.padding = padding
        self.border = border
        self.display = display
        self.align = align
        self.name = name
        # store the initial width and height but don't mutate
        self._width = width
        self._height = height

        # The size() method gets used in a lot of places, so cache the value when calculated.
        # This is more about making clearer logs than resource management.
        self._size: Optional[Tuple[int, int]] = None
        self._elements: List[Element] = []

        self._container_name = f"(Container name={self.name})"

    def __repr__(self):
        return f"(Container name={self.name}, size={self.size()}, " \
               f"border={self.border}, padding={self.padding}, display={self.display}, align={self.align}) "

    def add(self, element: Element):
        self._elements.append(element)
        # Reset the cached size value
        self._size = None

    def size(self) -> Tuple[int, int]:
        # Returned cached size value if available
        if self._size:
            return self._size

        height = self._height
        width = self._width

        # Initialized to zero in case an empty container is being used for spacing (bit of a hack)
        element_widths = 0
        element_heights = 0
        if len(self._elements):
            # if displaying in BLOCK style, elements are placed *vertically*, so adjust canvas to fit widest single
            # element if displaying in INLINE style, elements are placed *horizontally*, so adjust canvas to fit tallest
            # single element
            width_func = max if self.display is Display.BLOCK else sum
            height_func = sum if self.display is Display.BLOCK else max

            # Ignoring mypy complaints here, because succinctness seems more important
            element_widths = width_func([e.width() for e in self._elements])  # type: ignore
            element_heights = height_func([e.height() for e in self._elements])  # type: ignore

        total_width = element_widths + self.padding.left + self.padding.right
        total_height = element_heights + self.padding.top + self.padding.bottom

        # if the width is not specified, expand the canvas to fit elements and padding
        if self._width == 0:
            width = total_width
            log.debug(f"{self._container_name} expanding width to {width} to fit elements")
        else:
            if total_width > self._width:
                log.warning(f"{self._container_name} will have elements outside the visible canvas (w:{total_width})")

        # If the height is not specified, expand the canvas to fit elements and padding
        if self._height == 0:
            height = total_height
            log.debug(f"{self._container_name} expanding height to {height} to fit elements")
        else:
            if total_height > self._height:
                log.warning(f"{self._container_name} will have elements outside the visible canvas (h:{total_height})")

        if width < 0:
            raise ValueError(f"Invalid canvas width: {width}")
        if height < 0:
            raise ValueError(f"Invalid canvas height: {height}")

        log.debug(f"{self._container_name} width:{width}, height:{height}")

        self._size = width, height
        return self._size

    def boundaries(self) -> Tuple[int, int, int, int]:
        # Define the drawable boundaries based on padding
        # NOTE: padding fixed containers where the elements are too large will result in overflow.
        container_width, container_height = self.size()

        min_x = self.padding.left
        max_x = container_width - self.padding.right
        min_y = self.padding.top
        max_y = container_height - self.padding.bottom

        return min_x, min_y, max_x, max_y

    def elements(self) -> List[Element]:
        return self._elements


class Layout:
    """
    Calculates coordinates for each element in a Container.
    """

    def __init__(self, container: Container):
        self._container = container

    def __repr__(self):
        return f"(Layout container={self._container})"

    def _inline(self) -> LayoutList:
        layout: LayoutList = []
        min_x, min_y, max_x, max_y = self._container.boundaries()
        log.debug(f"{self._container} INLINE container with boundaries x:{min_x}->{max_x}, y:{min_y}->{max_y}")

        position = Position(x=min_x, y=min_y)

        if self._container.align is Align.LEFT:
            for element in self._container.elements():
                log.debug(f"{self._container} Placing {element} at {position}")
                layout.append((copy(position), element))
                position.x += element.width()

        if self._container.align is Align.RIGHT:
            position.x = max_x
            for element in self._container.elements():
                log.debug(f"{self._container} Placing {element} at {position}")
                position.x -= element.width()
                layout.append((copy(position), element))

        return layout

    def _block(self) -> LayoutList:
        layout: LayoutList = []
        min_x, min_y, max_x, max_y = self._container.boundaries()
        log.debug(f"{self._container} BLOCK container with boundaries x:{min_x}->{max_x}, y:{min_y}->{max_y}")

        position = Position(x=min_x, y=min_y)

        if self._container.align is Align.LEFT:
            for element in self._container.elements():
                log.debug(f"{self._container} Placing {element} at {position}")
                layout.append((copy(position), element))
                position.y += element.height()

        if self._container.align is Align.RIGHT:
            for element in self._container.elements():
                position.x = max_x
                position.x -= element.width()
                log.debug(f"{self._container} Placing {element} at {position}")
                layout.append((copy(position), element))
                position.y += element.height()

        return layout

    def layout(self) -> LayoutList:
        if self._container.display is Display.BLOCK:
            return self._block()
        elif self._container.display is Display.INLINE:
            return self._inline()
        else:
            log.error(f"{self._container.display} is not recognized, skipping (Container name={self._container.name})")
