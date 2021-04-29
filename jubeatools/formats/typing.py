from typing import Any, Callable, Dict, Protocol

from path import Path

from jubeatools.song import Song


class Dumper(Protocol):
    def __call__(self, song: Song, path: Path, **kwargs: Any) -> Dict[Path, bytes]:
        ...


# Loaders deserialize a Path to a Song object
# The Path can be a file or a folder depending on the format
Loader = Callable[[Path], Song]
