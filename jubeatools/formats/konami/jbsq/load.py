from functools import reduce
from pathlib import Path
from typing import Any, Optional

from jubeatools import song
from jubeatools.formats.load_tools import make_folder_loader

from .. import commons as konami
from ..load_tools import make_chart_from_events
from . import construct


def load_jbsq(path: Path, *, beat_snap: int = 240, **kwargs: Any) -> song.Song:
    files = load_folder(path)
    charts = [
        load_jbsq_file(bytes_, path, beat_snap=beat_snap)
        for path, bytes_ in files.items()
    ]
    return reduce(song.Song.merge, charts)


def load_file(path: Path) -> bytes:
    return path.read_bytes()


load_folder = make_folder_loader("*.jbsq", load_file)


def load_jbsq_file(
    bytes_: bytes, file_path: Path, *, beat_snap: int = 240
) -> song.Song:
    raw_data = construct.jbsq.parse(bytes_)
    events = [make_event_from_construct(e) for e in raw_data.events]
    chart = make_chart_from_events(events, beat_snap=beat_snap)
    dif = guess_difficulty(file_path.stem) or song.Difficulty.EXTREME
    return song.Song(metadata=song.Metadata(), charts={dif: chart})


def make_event_from_construct(e: construct.Event) -> konami.Event:
    return konami.Event(
        time=e.time_in_ticks,
        command=konami.Command[e.type_.name],
        value=e.value,
    )


def guess_difficulty(filename: str) -> Optional[song.Difficulty]:
    try:
        return song.Difficulty(filename[-3:].upper())
    except ValueError:
        return None
