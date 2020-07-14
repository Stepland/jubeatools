"""
Module containing all the load/dump code for all file formats
"""
from enum import Enum
from typing import IO, Callable, Dict

from path import Path

from jubeatools.song import Song

from .jubeat_analyser.mono_column import dump_mono_column, load_mono_column
from .memon import (
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    dump_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
    load_memon_legacy,
)


class Format(str, Enum):
    MEMON_LEGACY = "memon:legacy"
    MEMON_0_1_0 = "memon:v0.1.0"
    MEMON_0_2_0 = "memon:v0.2.0"
    MONO_COLUMN = "mono-column"


# Loaders deserialize a Path to a Song object
# The Path can be a file or a folder depending on the format
LOADERS: Dict[Format, Callable[[Path], Song]] = {
    Format.MEMON_LEGACY: load_memon_legacy,
    Format.MEMON_0_1_0: load_memon_0_1_0,
    Format.MEMON_0_2_0: load_memon_0_2_0,
    Format.MONO_COLUMN: load_mono_column,
}

DUMPERS: Dict[str, Callable[[Song], Dict[str, IO]]] = {
    Format.MEMON_LEGACY: dump_memon_legacy,
    Format.MEMON_0_1_0: dump_memon_0_1_0,
    Format.MEMON_0_2_0: dump_memon_0_2_0,
    Format.MONO_COLUMN: dump_mono_column,
}
