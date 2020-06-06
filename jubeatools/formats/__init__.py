"""
Module containing all the load/dump code for all file formats
"""
from path import Path
from typing import Callable, Dict, IO

from jubeatools.song import Song
from .memon import (
    dump_memon_legacy,
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    load_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
)

ALIASES = {
    "memon": "memon:v0.2.0",
}

# Loaders deserialize a folder or a file to a Song object
LOADERS: Dict[str, Callable[[Path], Song]] = {
    "memon:legacy": load_memon_legacy,
    "memon:v0.1.0": load_memon_0_1_0,
    "memon:v0.2.0": load_memon_0_2_0,
}

# Dumpers serialize a Song object into a (filename -> file) mapping
DUMPERS: Dict[str, Callable[[Song], Dict[str, IO]]] = {
    "memon:legacy": dump_memon_legacy,
    "memon:v0.1.0": dump_memon_0_1_0,
    "memon:v0.2.0": dump_memon_0_2_0,
}
