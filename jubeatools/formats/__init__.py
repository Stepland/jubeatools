"""
Base class for all file formats
"""
from path import Path
from typing import Any, Callable, Iterable, Tuple, IO

from jubeatools.song import Song
from .memon import *
from ._filekind import FileKind

ALIASES = {
    "memon": "memon:v0.2.0",
}

# Loaders take in a folder containing the files to be converted
# and return a Song object
LOADERS: Mapping[str, Callable[[Path], Song]] = {
    "memon:legacy": load_memon_legacy,
    "memon:v0.1.0": load_memon_0_1_0,
    "memon:v0.2.0": load_memon_0_2_0
}

# Dumpers take in the song object and return a list of tuples
DUMPERS: Mapping[str, Callable[[Song], Iterable[Tuple[Any, IO]]]] = {
    "memon:legacy": dump_memon_legacy,
    "memon:v0.1.0": dump_memon_0_1_0,
    "memon:v0.2.0": dump_memon_0_2_0
}