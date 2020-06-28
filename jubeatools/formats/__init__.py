"""
Module containing all the load/dump code for all file formats
"""
from typing import IO, Callable, Dict

from path import Path

from jubeatools.song import Song

from .memo.mono_column import load_mono_column
from .memon import (
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    dump_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
    load_memon_legacy,
)

ALIASES = {
    "memon": "memon:v0.2.0",
    "ichi-retsu": "mono-column",
}

# Loaders deserialize a Path to a Song object
# The Path can be a file or a folder depending on the format
LOADERS: Dict[str, Callable[[Path], Song]] = {
    "memon:legacy": load_memon_legacy,
    "memon:v0.1.0": load_memon_0_1_0,
    "memon:v0.2.0": load_memon_0_2_0,
    "mono-column": load_mono_column,
}

# Dumpers serialize a Song object into a (filename -> file) mapping
DUMPERS: Dict[str, Callable[[Song], Dict[str, IO]]] = {
    "memon:legacy": dump_memon_legacy,
    "memon:v0.1.0": dump_memon_0_1_0,
    "memon:v0.2.0": dump_memon_0_2_0,
}
