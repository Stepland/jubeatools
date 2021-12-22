import string
from functools import singledispatch
from itertools import count
from pathlib import Path
from typing import AbstractSet, Any, Dict, Iterator, Optional, TypedDict

from jubeatools.formats.filetypes import ChartFile, JubeatFile, SongFile
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
        name_format = FileNameFormat(file_name_template, suggestion=path)
        files = internal_dumper(song, **kwargs)
        for chartfile in files:
            filepath = name_format.available_filename_for(
                chartfile, already_chosen=res.keys()
            )
            res[filepath] = chartfile.contents

        return res

    return dumper


class FormatParameters(TypedDict, total=False):
    title: str
    # uppercase BSC ADV EXT
    difficulty: str
    # 0-based
    difficulty_index: str
    # 1-based
    difficulty_number: str
    dedup: str


class FileNameFormat:
    def __init__(self, file_name_template: Path, suggestion: Path):
        if suggestion.is_dir():
            file_path = file_name_template
            self.parent = suggestion
        else:
            file_path = suggestion
            self.parent = suggestion.parent

        self.name_format = f"{file_path.stem}{{dedup}}{file_path.suffix}"

    def available_filename_for(
        self, file: JubeatFile, already_chosen: Optional[AbstractSet[Path]] = None
    ) -> Path:
        fixed_params = extract_format_params(file)
        return next(self.iter_possible_paths(fixed_params, already_chosen))

    def iter_possible_paths(
        self,
        fixed_params: FormatParameters,
        already_chosen: Optional[AbstractSet[Path]] = None,
    ) -> Iterator[Path]:
        all_paths = self.iter_deduped_paths(fixed_params)
        not_on_filesystem = (p for p in all_paths if not p.exists())
        if already_chosen is not None:
            yield from (p for p in not_on_filesystem if p not in already_chosen)
        else:
            yield from not_on_filesystem

    def iter_deduped_paths(self, params: FormatParameters) -> Iterator[Path]:
        for dedup_index in count(start=0):
            # TODO Remove the type ignore once this issue is fixed
            # https://github.com/python/mypy/issues/6019
            params.update(  # type: ignore[call-arg]
                dedup="" if dedup_index == 0 else f"-{dedup_index}"
            )
            formatter = BetterStringFormatter()
            filename = formatter.format(self.name_format, **params).strip()
            yield self.parent / filename


@singledispatch
def extract_format_params(file: JubeatFile) -> FormatParameters:
    ...


@extract_format_params.register
def extract_song_format_params(songfile: SongFile) -> FormatParameters:
    return FormatParameters(title=none_or(slugify, songfile.song.metadata.title) or "")


@extract_format_params.register
def extract_chart_format_params(chartfile: ChartFile) -> FormatParameters:
    return FormatParameters(
        title=none_or(slugify, chartfile.song.metadata.title) or "",
        difficulty=slugify(chartfile.difficulty),
        difficulty_index=str(DIFFICULTY_INDEX.get(chartfile.difficulty, 2)),
        difficulty_number=str(DIFFICULTY_NUMBER.get(chartfile.difficulty, 3)),
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
