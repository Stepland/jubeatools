from io import StringIO
from itertools import chain
from typing import Any, Dict, List, Union

import simplejson as json

from jubeatools import song as jbt
from jubeatools.formats.filetypes import SongFile
from jubeatools.utils import lcm

from ..tools import make_memon_dumper
from . import schema


def _long_note_tail_value_v0(note: jbt.LongNote) -> int:
    dx = note.tail_tip.x - note.position.x
    dy = note.tail_tip.y - note.position.y
    try:
        return schema.X_Y_OFFSET_TO_P_VALUE[dx, dy]
    except KeyError:
        raise ValueError(
            f"memon cannot represent a long note with its tail starting ({dx}, {dy}) away from the note"
        ) from None


def _get_timing(song: jbt.Song) -> jbt.Timing:
    if song.common_timing is not None:
        return song.common_timing
    else:
        return next(
            chart.timing for chart in song.charts.values() if chart.timing is not None
        )


def _raise_if_unfit_for_v0(song: jbt.Song, version: str) -> None:
    """Raises an exception if the Song object is ill-formed or contains information
    that cannot be represented in a memon v0.x.y file (includes legacy)"""

    if song.common_timing is None and all(
        chart.timing is None for chart in song.charts.values()
    ):
        raise ValueError("The song has no timing information")

    chart_timings = [
        chart.timing for chart in song.charts.values() if chart.timing is not None
    ]

    if chart_timings:
        first_one = chart_timings[0]
        if any(t != first_one for t in chart_timings):
            raise ValueError(
                f"memon:{version} cannot represent a song with per-chart timing"
            )

    timing = _get_timing(song)
    number_of_timing_events = len(timing.events)
    if number_of_timing_events != 1:
        if number_of_timing_events == 0:
            raise ValueError("The song has no BPM")
        else:
            raise ValueError(f"memon:{version} does not handle BPM changes")

    event = timing.events[0]
    if event.BPM <= 0:
        raise ValueError(f"memon:{version} only accepts strictly positive BPMs")

    if event.time != 0:
        raise ValueError(f"memon:{version} only accepts a BPM on the first beat")

    for difficulty, chart in song.charts.items():
        if len(set(chart.notes)) != len(chart.notes):
            raise ValueError(
                f"{difficulty} chart has duplicate notes, these cannot be represented"
            )


def _dump_to_json(memon: dict) -> bytes:
    memon_fp = StringIO()
    json.dump(memon, memon_fp, use_decimal=True, indent=4)
    return memon_fp.getvalue().encode("utf-8")


def _compute_resolution(notes: List[Union[jbt.TapNote, jbt.LongNote]]) -> int:
    return lcm(
        *chain(
            iter(note.time.denominator for note in notes),
            iter(
                note.duration.denominator
                for note in notes
                if isinstance(note, jbt.LongNote)
            ),
        )
    )


def _dump_memon_note_v0(
    note: Union[jbt.TapNote, jbt.LongNote], resolution: int
) -> Dict[str, int]:
    """converts a note into the {n, t, l, p} form"""
    memon_note = {
        "n": note.position.index,
        "t": note.time.numerator * (resolution // note.time.denominator),
        "l": 0,
        "p": 0,
    }
    if isinstance(note, jbt.LongNote):
        memon_note["l"] = note.duration.numerator * (
            resolution // note.duration.denominator
        )
        memon_note["p"] = _long_note_tail_value_v0(note)

    return memon_note


def _dump_memon_legacy(song: jbt.Song, **kwargs: Any) -> SongFile:
    _raise_if_unfit_for_v0(song, "legacy")
    timing = _get_timing(song)

    memon: Dict[str, Any] = {
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "jacket path": str(song.metadata.cover),
            "BPM": timing.events[0].BPM,
            "offset": -timing.beat_zero_offset,
        },
        "data": [],
    }
    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"].append(
            {
                "dif_name": difficulty,
                "level": chart.level,
                "resolution": resolution,
                "notes": [
                    _dump_memon_note_v0(note, resolution)
                    for note in sorted(
                        set(chart.notes), key=lambda n: (n.time, n.position)
                    )
                ],
            }
        )

    return SongFile(contents=_dump_to_json(memon), song=song)


dump_memon_legacy = make_memon_dumper(_dump_memon_legacy)


def _dump_memon_0_1_0(song: jbt.Song, **kwargs: Any) -> SongFile:
    _raise_if_unfit_for_v0(song, "v0.1.0")
    timing = _get_timing(song)

    memon: Dict[str, Any] = {
        "version": "0.1.0",
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "album cover path": str(song.metadata.cover),
            "BPM": timing.events[0].BPM,
            "offset": -timing.beat_zero_offset,
        },
        "data": dict(),
    }
    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"][difficulty] = {
            "level": chart.level,
            "resolution": resolution,
            "notes": [
                _dump_memon_note_v0(note, resolution)
                for note in sorted(set(chart.notes), key=lambda n: (n.time, n.position))
            ],
        }

    return SongFile(contents=_dump_to_json(memon), song=song)


dump_memon_0_1_0 = make_memon_dumper(_dump_memon_0_1_0)


def _dump_memon_0_2_0(song: jbt.Song, **kwargs: Any) -> SongFile:
    _raise_if_unfit_for_v0(song, "v0.2.0")
    timing = _get_timing(song)

    memon: Dict[str, Any] = {
        "version": "0.2.0",
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "album cover path": str(song.metadata.cover),
            "BPM": timing.events[0].BPM,
            "offset": -timing.beat_zero_offset,
        },
        "data": {},
    }

    if song.metadata.preview is not None:
        memon["metadata"]["preview"] = {
            "position": song.metadata.preview.start,
            "length": song.metadata.preview.length,
        }

    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"][difficulty] = {
            "level": chart.level,
            "resolution": resolution,
            "notes": [
                _dump_memon_note_v0(note, resolution)
                for note in sorted(set(chart.notes), key=lambda n: (n.time, n.position))
            ],
        }

    return SongFile(contents=_dump_to_json(memon), song=song)


dump_memon_0_2_0 = make_memon_dumper(_dump_memon_0_2_0)


def _dump_memon_0_3_0(song: jbt.Song, **kwargs: Any) -> SongFile:
    _raise_if_unfit_for_v0(song, "v0.3.0")
    timing = _get_timing(song)

    memon: Dict[str, Any] = {
        "version": "0.3.0",
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "BPM": timing.events[0].BPM,
            "offset": -timing.beat_zero_offset,
        },
        "data": {},
    }

    if song.metadata.audio is not None:
        memon["metadata"]["music path"] = str(song.metadata.audio)

    if song.metadata.cover is not None:
        memon["metadata"]["album cover path"] = str(song.metadata.cover)

    if song.metadata.preview is not None:
        memon["metadata"]["preview"] = {
            "position": song.metadata.preview.start,
            "length": song.metadata.preview.length,
        }

    if song.metadata.preview_file is not None:
        memon["metadata"]["preview path"] = str(song.metadata.preview_file)

    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"][difficulty] = {
            "level": chart.level,
            "resolution": resolution,
            "notes": [
                _dump_memon_note_v0(note, resolution)
                for note in sorted(set(chart.notes), key=lambda n: (n.time, n.position))
            ],
        }

    return SongFile(contents=_dump_to_json(memon), song=song)


dump_memon_0_3_0 = make_memon_dumper(_dump_memon_0_3_0)
