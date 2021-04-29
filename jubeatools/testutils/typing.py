from typing import Callable, TypeVar

from hypothesis.strategies import SearchStrategy

T = TypeVar("T")
DrawFunc = Callable[[SearchStrategy[T]], T]
