from abc import ABC, abstractmethod
from typing import Tuple


class Element(ABC):
    """
    Define the minimum interface needed for operations
    """

    @abstractmethod
    def size(self) -> Tuple[int, int]:
        pass

    def width(self) -> int:
        return self.size()[0]

    def height(self) -> int:
        return self.size()[1]
