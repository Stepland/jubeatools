from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Dict, Iterable, Optional, Protocol, TypeVar, Union

from jubeatools import song

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class FileLoader(Protocol[T_co]):
    """Function that excepts a path to a file as a parameter and returns its
    contents in whatever form suitable for the current format. Returns None in
    case of error"""

    def __call__(self, path: Path) -> Optional[T_co]:
        ...


class FolderLoader(Protocol[T]):
    """Function that expects a folder or a file path as a parameter. Loads
    either all valid files in the folder or just the given file depending on
    the argument"""

    def __call__(self, path: Path) -> Dict[Path, T]:
        ...


def make_folder_loader(
    glob_pattern: str, file_loader: FileLoader[T]
) -> FolderLoader[T]:
    def folder_loader(path: Path) -> Dict[Path, T]:
        files: Dict[Path, T] = {}
        if path.is_dir():
            paths: Iterable[Path] = path.glob(glob_pattern)
        else:
            paths = [path]

        for p in paths:
            value = file_loader(p)
            if value is not None:
                files[p] = value

        return files

    return folder_loader


# TODO
# use numbers.Number instead when this mypy issue is finally fixed
# https://github.com/python/mypy/issues/3186
Number = Union[int, float, Decimal, Fraction]


def round_beats(beats: Number, denominator: int = 240) -> song.BeatsTime:
    """Rounds a given beat value to the nearest given division (default to
    nearest 1/240th"""
    nearest = round(beats * denominator)
    return song.BeatsTime(nearest, denominator)
