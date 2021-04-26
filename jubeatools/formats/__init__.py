"""
Module containing all the load/dump code for all file formats
"""

from typing import IO, Any, Callable, Dict

from path import Path

from jubeatools.song import Song

from .enum import Format
from .jubeat_analyser import (
    dump_memo,
    dump_memo1,
    dump_memo2,
    dump_mono_column,
    load_memo,
    load_memo1,
    load_memo2,
    load_mono_column,
)
from .memon import (
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    dump_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
    load_memon_legacy,
)
from .typing import Dumper

# Loaders deserialize a Path to a Song object
# The Path can be a file or a folder depending on the format
LOADERS: Dict[Format, Callable[[Path], Song]] = {
    Format.MEMON_LEGACY: load_memon_legacy,
    Format.MEMON_0_1_0: load_memon_0_1_0,
    Format.MEMON_0_2_0: load_memon_0_2_0,
    Format.MONO_COLUMN: load_mono_column,
    Format.MEMO: load_memo,
    Format.MEMO_1: load_memo1,
    Format.MEMO_2: load_memo2,
}

DUMPERS: Dict[str, Dumper] = {
    Format.MEMON_LEGACY: dump_memon_legacy,
    Format.MEMON_0_1_0: dump_memon_0_1_0,
    Format.MEMON_0_2_0: dump_memon_0_2_0,
    Format.MONO_COLUMN: dump_mono_column,
    Format.MEMO: dump_memo,
    Format.MEMO_1: dump_memo1,
    Format.MEMO_2: dump_memo2,
}
