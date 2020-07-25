from typing import Any, Dict, Protocol

from path import Path

from jubeatools.song import Song


class Dumper(Protocol):
    def __call__(
        self, song: Song, path: Path, **kwargs: Dict[str, Any]
    ) -> Dict[Path, bytes]:
        ...
