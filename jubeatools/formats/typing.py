from pathlib import Path
from typing import Any, Callable, Dict, Protocol

from jubeatools.song import Song


# Dumpers take a Song object and a Path hint and give back a dict that maps
#
class Dumper(Protocol):
    """A Dumper is a callable that takes in a Song object, a Path hint and
    potential options, then gives back a dict that maps file name suggestions
    to the binary content of the file"""

    def __call__(self, song: Song, path: Path, **kwargs: Any) -> Dict[Path, bytes]:
        ...


# Loaders deserialize a Path to a Song object
# The Path can be a file or a folder depending on the format
Loader = Callable[[Path], Song]
