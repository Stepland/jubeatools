from functools import reduce
from pathlib import Path
from typing import Any, Iterator, List, Optional

from jubeatools import song
from jubeatools.formats.load_tools import make_folder_loader

from ..commons import Command, Event
from ..load_tools import make_chart_from_events


def load_eve(path: Path, *, beat_snap: int = 240, **kwargs: Any) -> song.Song:
    files = load_folder(path)
    charts = [_load_eve(l, p, beat_snap=beat_snap) for p, l in files.items()]
    return reduce(song.Song.merge, charts)


def load_file(path: Path) -> List[str]:
    return path.read_text(encoding="ascii").split("\n")


load_folder = make_folder_loader("*.eve", load_file)


def _load_eve(lines: List[str], file_path: Path, *, beat_snap: int = 240) -> song.Song:
    chart = make_chart_from_events(iter_events(lines), beat_snap=beat_snap)
    dif = guess_difficulty(file_path.stem) or song.Difficulty.EXTREME
    return song.Song(metadata=song.Metadata(), charts={dif: chart})


def iter_events(lines: List[str]) -> Iterator[Event]:
    for i, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        try:
            yield parse_event(line)
        except ValueError as e:
            raise ValueError(f"Error on line {i} : {e}")


def parse_event(line: str) -> Event:
    columns = line.split(",")
    if len(columns) != 3:
        raise ValueError(f"Expected 3 comma-separated values but found {len(columns)}")

    raw_tick, raw_command, raw_value = map(str.strip, columns)
    try:
        tick = int(raw_tick)
    except ValueError:
        raise ValueError(
            f"The first column should contain an integer but {raw_tick!r} was "
            f"found, which python could not understand as an integer"
        )

    try:
        command = Command[raw_command]
    except KeyError:
        raise ValueError(
            f"The second column should contain one of "
            f"{list(Command.__members__)}, but {raw_command!r} was found"
        )

    try:
        value = int(raw_value)
    except ValueError:
        raise ValueError(
            f"The third column should contain an integer but {raw_tick!r} was "
            f"found, which python could not understand as an integer"
        )

    return Event(tick, command, value)


def guess_difficulty(filename: str) -> Optional[song.Difficulty]:
    try:
        return song.Difficulty(filename.upper())
    except ValueError:
        return None
