import warnings
from decimal import Decimal
from fractions import Fraction
from functools import reduce, singledispatch
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import simplejson as json

from jubeatools import song
from jubeatools.formats import timemap
from jubeatools.formats.load_tools import make_folder_loader
from jubeatools.utils import none_or

from . import schema as malody


def load_malody(path: Path, **kwargs: Any) -> song.Song:
    files = load_folder(path)
    charts = [load_malody_file(d) for d in files.values()]
    return reduce(song.Song.merge, charts)


def load_file(path: Path) -> Any:
    with path.open() as f:
        return json.load(f, use_decimal=True)


load_folder = make_folder_loader("*.mc", load_file)


def load_malody_file(raw_dict: dict) -> song.Song:
    file: malody.Chart = malody.CHART_SCHEMA.load(raw_dict)
    if file.meta.mode != malody.Mode.PAD:
        raise ValueError("This file is not a Malody Pad Chart (Malody's jubeat mode)")

    bgm = find_bgm(file.note)
    metadata = load_metadata(file.meta, bgm)
    time_map = load_timing_info(file.time, bgm)
    timing = time_map.convert_to_timing_info()
    chart = song.Chart(level=Decimal(0), timing=timing, notes=load_notes(file.note))
    dif = file.meta.version or song.Difficulty.EXTREME
    return song.Song(metadata=metadata, charts={dif: chart})


def find_bgm(events: List[malody.Event]) -> Optional[malody.Sound]:
    sounds = [e for e in events if isinstance(e, malody.Sound)]
    bgms = [s for s in sounds if s.type == malody.SoundType.BACKGROUND_MUSIC]
    if not bgms:
        return None

    if len(bgms) > 1:
        warnings.warn(
            "This file defines more than one background music, the first one "
            "will be used"
        )

    return min(bgms, key=lambda b: tuple_to_beats(b.beat))


def load_metadata(meta: malody.Metadata, bgm: Optional[malody.Sound]) -> song.Metadata:
    return song.Metadata(
        title=meta.song.title,
        artist=meta.song.artist,
        audio=none_or(lambda b: Path(b.sound), bgm),
        cover=none_or(Path, meta.background),
    )


def load_timing_info(
    bpm_changes: List[malody.BPMEvent], bgm: Optional[malody.Sound]
) -> timemap.TimeMap:
    if bgm is None:
        offset = timemap.SecondsAtBeat(seconds=Fraction(0), beats=Fraction(0))
    else:
        offset = timemap.SecondsAtBeat(
            seconds=-Fraction(bgm.offset) / 1000, beats=tuple_to_beats(bgm.beat)
        )
    return timemap.TimeMap.from_beats(
        events=[
            timemap.BPMAtBeat(beats=tuple_to_beats(b.beat), BPM=Fraction(b.bpm))
            for b in bpm_changes
        ],
        offset=offset,
    )


def load_notes(events: List[malody.Event]) -> List[Union[song.TapNote, song.LongNote]]:
    # filter out sound events
    notes = filter(lambda e: isinstance(e, (malody.TapNote, malody.LongNote)), events)
    return [load_note(n) for n in notes]


@singledispatch
def load_note(
    n: Union[malody.TapNote, malody.LongNote]
) -> Union[song.TapNote, song.LongNote]:
    raise NotImplementedError(f"Unknown note type : {type(n)}")


@load_note.register
def load_tap_note(n: malody.TapNote) -> song.TapNote:
    return song.TapNote(
        time=tuple_to_beats(n.beat), position=song.NotePosition.from_index(n.index)
    )


@load_note.register
def load_long_note(n: malody.LongNote) -> song.LongNote:
    start = tuple_to_beats(n.beat)
    end = tuple_to_beats(n.endbeat)
    return song.LongNote(
        time=start,
        position=song.NotePosition.from_index(n.index),
        duration=end - start,
        tail_tip=song.NotePosition.from_index(n.endindex),
    )


def tuple_to_beats(b: Tuple[int, int, int]) -> song.BeatsTime:
    return b[0] + song.BeatsTime(b[1], b[2])
