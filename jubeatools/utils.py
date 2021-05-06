"""General utility functions"""

import unicodedata
from decimal import Decimal
from fractions import Fraction
from functools import reduce
from math import gcd
from typing import Callable, Optional, TypeVar, List, Dict
from collections import defaultdict


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

# Monadic stuff !
def none_or(c: Callable[[A], B], e: Optional[A]) -> Optional[B]:
    if e is None:
        return None
    else:
        return c(e)


def fraction_to_decimal(frac: Fraction) -> Decimal:
    "Thanks stackoverflow ! https://stackoverflow.com/a/40468867/10768117"
    return frac.numerator / Decimal(frac.denominator)


K = TypeVar("K")
V = TypeVar("V")


def group_by(elements: List[V], key: Callable[[V], K]) -> Dict[K, List[V]]:
    res = defaultdict(list)
    for e in elements:
        res[key(e)].append(e)

    return res
