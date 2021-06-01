import string
from itertools import count
from pathlib import Path
from typing import AbstractSet, Any, Dict, Iterator, TypedDict

from jubeatools.formats.filetypes import ChartFile
from jubeatools.formats.typing import ChartFileDumper, Dumper
from jubeatools.song import Difficulty, Song
from jubeatools.utils import none_or

DIFFICULTY_NUMBER: Dict[str, int] = {
    Difficulty.BASIC: 1,
    Difficulty.ADVANCED: 2,
    Difficulty.EXTREME: 3,
}

DIFFICULTY_INDEX: Dict[str, int] = {
    Difficulty.BASIC: 0,
    Difficulty.ADVANCED: 1,
    Difficulty.EXTREME: 2,
}


def make_dumper_from_chart_file_dumper(
    internal_dumper: ChartFileDumper,
    file_name_template: Path,
) -> Dumper:
    """Adapt a ChartFileDumper to the Dumper protocol, The resulting function
    uses the file name template if it recieves an existing directory as an
    output path"""

    def dumper(song: Song, path: Path, **kwargs: Any) -> Dict[Path, bytes]:
        res: Dict[Path, bytes] = {}
        if path.is_dir():
            file_path = file_name_template
            parent = path
        else:
            file_path = path
            parent = path.parent

        name_format = f"{file_path.stem}{{dedup}}{file_path.suffix}"
        files = internal_dumper(song, **kwargs)
        for chartfile in files:
            filepath = choose_file_path(chartfile, name_format, parent, res.keys())
            res[filepath] = chartfile.contents

        return res

    return dumper


def choose_file_path(
    chart_file: ChartFile,
    name_format: str,
    parent: Path,
    already_chosen: AbstractSet[Path],
) -> Path:
    all_paths = iter_possible_paths(chart_file, name_format, parent)
    not_on_filesystem = filter(lambda p: not p.exists(), all_paths)
    not_already_chosen = filter(lambda p: p not in already_chosen, not_on_filesystem)
    return next(not_already_chosen)


def iter_possible_paths(
    chart_file: ChartFile, name_format: str, parent: Path
) -> Iterator[Path]:
    for dedup_index in count(start=0):
        params = extract_format_params(chart_file, dedup_index)
        formatter = BetterStringFormatter()
        filename = formatter.format(name_format, **params).strip()
        yield parent / filename


class FormatParameters(TypedDict, total=False):
    title: str
    # uppercase BSC ADV EXT
    difficulty: str
    # 0-based
    difficulty_index: str
    # 1-based
    difficulty_number: str
    dedup: str


def extract_format_params(chartfile: ChartFile, dedup_index: int) -> FormatParameters:
    return FormatParameters(
        title=none_or(slugify, chartfile.song.metadata.title) or "",
        difficulty=slugify(chartfile.difficulty),
        difficulty_index=str(DIFFICULTY_INDEX.get(chartfile.difficulty, 2)),
        difficulty_number=str(DIFFICULTY_NUMBER.get(chartfile.difficulty, 3)),
        dedup="" if dedup_index == 0 else f"-{dedup_index}",
    )


def slugify(s: str) -> str:
    s = remove_slashes(s)
    s = double_braces(s)
    return s


SLASHES = str.maketrans({"/": "", "\\": ""})


def remove_slashes(s: str) -> str:
    return s.translate(SLASHES)


BRACES = str.maketrans({"{": "{{", "}": "}}"})


def double_braces(s: str) -> str:
    return s.translate(BRACES)


class BetterStringFormatter(string.Formatter):
    """Enables the use of 'u' and 'l' suffixes in string format specifiers to
    convert the string to uppercase or lowercase
    Thanks stackoverflow ! https://stackoverflow.com/a/57570269/10768117
    """

    def format_field(self, value: Any, format_spec: str) -> str:
        if isinstance(value, str):
            if format_spec.endswith("u"):
                value = value.upper()
                format_spec = format_spec[:-1]
            elif format_spec.endswith("l"):
                value = value.lower()
                format_spec = format_spec[:-1]
        return super().format(value, format_spec)
