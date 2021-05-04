import unicodedata
from functools import reduce
from math import gcd
from typing import Callable, Optional, TypeVar


def single_lcm(a: int, b: int) -> int:
    """Return lowest common multiple of two numbers"""
    return a * b // gcd(a, b)


def lcm(*args: int) -> int:
    """Return lcm of args."""
    return reduce(single_lcm, args, 1)


def charinfo(c: str) -> str:
    """Return some info on the character"""
    return f"{c!r}  # U+{ord(c):05X} : {unicodedata.name(c)}"


A = TypeVar("A")
B = TypeVar("B")


def none_or(c: Callable[[A], B], e: Optional[A]) -> Optional[B]:
    if e is None:
        return None
    else:
        return c(e)
