from functools import reduce
from math import gcd


def single_lcm(a: int, b: int):
    """Return lowest common multiple of two numbers"""
    return a * b // gcd(a, b)


def lcm(*args):
    """Return lcm of args."""
    return reduce(single_lcm, args, 1)
