from pathlib import Path
from typing import Any, Dict, List, Protocol

from jubeatools.formats.filetypes import ChartFile, SongFile
from jubeatools.song import Song


# Dumpers take a Song object and a Path hint and give back a dict that maps
#
class Dumper(Protocol):
    """A Dumper is a callable that takes in a Song object, a Path hint and
    potential options, then gives back a dict that maps file name suggestions
    to the binary content of the file"""

    def __call__(self, song: Song, path: Path, **kwargs: Any) -> Dict[Path, bytes]:
        ...


class ChartFileDumper(Protocol):
    """Generic signature of internal dumper for formats that use one file
    per chart"""

    def __call__(self, song: Song, **kwargs: Any) -> List[ChartFile]:
        ...


class SongFileDumper(Protocol):
    """Generic signature of internal dumper for formats that use a single file
    to hold all charts of a song"""

    def __call__(self, song: Song, **kwargs: Any) -> SongFile:
        ...


class Loader(Protocol):
    """A Loader deserializes a Path to a Song object and possibly takes in
    some options via the kwargs.
    The Path can be a file or a folder depending on the format"""

    def __call__(self, path: Path, **kwargs: Any) -> Song:
        ...
