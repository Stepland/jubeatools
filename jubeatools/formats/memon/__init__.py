"""
memon (memo + json)
□□□■——◁

memon is a json-based jubeat chart set format designed to be easier to
parse than existing "memo-like" formats (memo, youbeat, etc ...).

https://github.com/Stepland/memon
"""

from .memon import (
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    dump_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
    load_memon_legacy,
)
