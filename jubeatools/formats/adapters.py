"""Things that make it easier to integrate formats with different opinions
on song folder structure"""

from itertools import count
from typing import TypedDict, Iterator, Any, Dict, AbstractSet
from pathlib import Path

from jubeatools.song import Song
from jubeatools.formats.typing import ChartFileDumper, Dumper
from jubeatools.formats.filetypes import ChartFile
from jubeatools.formats.dump_tools import DIFFICULTY_INDEX, DIFFICULTY_NUMBER


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
        else:
            file_path = path

        name_format = f"{file_path.stem}{{dedup}}{file_path.suffix}"
        files = internal_dumper(song, **kwargs)
        for chartfile in files:
            filepath = choose_file_path(chartfile, name_format, path.parent, res.keys())
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
        filename = name_format.format(**params).strip()
        yield parent / filename


class FormatParameters(TypedDict, total=False):
    title: str
    difficulty: str
    # 0-based
    difficulty_index: int
    # 1-based
    difficulty_number: int
    dedup: str


def extract_format_params(chartfile: ChartFile, dedup_index: int) -> FormatParameters:
    return FormatParameters(
        title=chartfile.song.metadata.title or "",
        difficulty=chartfile.difficulty,
        difficulty_index=DIFFICULTY_INDEX.get(chartfile.difficulty, 3),
        difficulty_number=DIFFICULTY_NUMBER.get(chartfile.difficulty, 4),
        dedup="" if dedup_index else f"-{dedup_index}",
    )
