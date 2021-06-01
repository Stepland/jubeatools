import time
from functools import singledispatch
from pathlib import Path
from typing import List, Optional, Tuple, Union

import simplejson as json

from jubeatools import song
from jubeatools.formats.dump_tools import make_dumper_from_chart_file_dumper
from jubeatools.formats.filetypes import ChartFile
from jubeatools.utils import none_or

from . import schema as malody


def dump_malody_song(song: song.Song, **kwargs: dict) -> List[ChartFile]:
    res = []
    for dif, chart, timing in song.iter_charts_with_timing():
        malody_chart = dump_malody_chart(song.metadata, dif, chart, timing)
        json_chart = malody.CHART_SCHEMA.dump(malody_chart)
        chart_bytes = json.dumps(json_chart, indent=4, use_decimal=True).encode("utf-8")
        res.append(ChartFile(chart_bytes, song, dif, chart))

    return res


dump_malody = make_dumper_from_chart_file_dumper(
    internal_dumper=dump_malody_song, file_name_template=Path("{difficulty:l}.mc")
)


def dump_malody_chart(
    metadata: song.Metadata, dif: Optional[str], chart: song.Chart, timing: song.Timing
) -> malody.Chart:
    meta = dump_metadata(metadata, dif)
    time = dump_timing(timing)
    notes = dump_notes(chart.notes)
    if metadata.audio is not None:
        notes += [dump_bgm(metadata.audio, timing)]
    return malody.Chart(meta=meta, time=time, note=notes)


def dump_metadata(metadata: song.Metadata, dif: Optional[str]) -> malody.Metadata:
    return malody.Metadata(
        cover=None,
        creator=None,
        background=none_or(str, metadata.cover),
        version=dif,
        id=0,
        mode=malody.Mode.PAD,
        time=int(time.time()),
        song=malody.SongInfo(
            title=metadata.title,
            artist=metadata.artist,
            id=0,
        ),
    )


def dump_timing(timing: song.Timing) -> List[malody.BPMEvent]:
    sorted_events = sorted(timing.events, key=lambda e: e.time)
    return [dump_bpm_change(e) for e in sorted_events]


def dump_bpm_change(b: song.BPMEvent) -> malody.BPMEvent:
    return malody.BPMEvent(
        beat=beats_to_tuple(b.time),
        bpm=b.BPM,
    )


def dump_notes(notes: List[Union[song.TapNote, song.LongNote]]) -> List[malody.Event]:
    return [dump_note(n) for n in notes]


@singledispatch
def dump_note(
    n: Union[song.TapNote, song.LongNote]
) -> Union[malody.TapNote, malody.LongNote]:
    raise NotImplementedError(f"Unknown note type : {type(n)}")


@dump_note.register
def dump_tap_note(n: song.TapNote) -> malody.TapNote:
    return malody.TapNote(
        beat=beats_to_tuple(n.time),
        index=n.position.index,
    )


@dump_note.register
def dump_long_note(n: song.LongNote) -> malody.LongNote:
    return malody.LongNote(
        beat=beats_to_tuple(n.time),
        index=n.position.index,
        endbeat=beats_to_tuple(n.time + n.duration),
        endindex=n.tail_tip.index,
    )


def dump_bgm(audio: Path, timing: song.Timing) -> malody.Sound:
    return malody.Sound(
        beat=beats_to_tuple(song.BeatsTime(0)),
        sound=str(audio),
        vol=100,
        offset=-int(timing.beat_zero_offset * 1000),
        type=malody.SoundType.BACKGROUND_MUSIC,
        isBgm=None,
        x=None,
    )


def beats_to_tuple(b: song.BeatsTime) -> Tuple[int, int, int]:
    integer_part = int(b)
    remainder = b % 1
    return (
        integer_part,
        remainder.numerator,
        remainder.denominator,
    )
