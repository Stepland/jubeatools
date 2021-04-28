from typing import Any, Dict, Callable

from pathlib import Path

from jubeatools.song import Song


Dumper = Callable[[Song, Path], Dict[Path, bytes]]