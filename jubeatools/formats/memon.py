"""
memon (memo + json)
□□□■——◁

memon is a json-based jubeat chart set format designed to be easier to
parse than existing "memo-like" formats (memo, youbeat, etc ...).

https://github.com/Stepland/memon
"""

import warnings
from path import Path
from typing import Mapping, IO, Iterable, Tuple, Any, Dict, Union, List
from io import BytesIO
from itertools import chain

import simplejson as json

from jubeatools.song import Song, BPMChange, TapNote, LongNote
from jubeatools.utils import lcm

# v0.x.x long note value :
#
#         8
#         4
#         0
#  11 7 3 . 1 5 9 
#         2
#         6
#        10

LONG_NOTE_VALUE_V0 = {
    (0, -1): 0,
    (0, -2): 4,
    (0, -3): 8,
    (0, 1): 2,
    (0, 2): 6,
    (0, 3): 10,
    (1, 0): 1,
    (2, 0): 5,
    (3, 0): 9,
    (-1, 0): 3,
    (-2, 0): 7,
    (-3, 0): 11
}


def load_memon_legacy(file_or_folder: Path) -> Song:
    ...


def load_memon_0_1_0(file_or_folder: Path) -> Song:
    ...


def load_memon_0_2_0(file_or_folder: Path) -> Song:
    ...


def _long_note_tail_value_v0(note: LongNote) -> int:
    dx = note.tail_tip.x - note.position.x
    dy = note.tail_tip.y - note.position.y
    try:
        return LONG_NOTE_VALUE_V0[dx, dy]
    except KeyError:
        raise ValueError(f"memon cannot represent a long note with its tail starting ({dx}, {dy}) away from the note") from None

def check_representable_in_v0(song: Song, version: str) -> None:
    
    """Raises an exception if the Song object is ill-formed or contains information
    that cannot be represented in a memon v0.x.x file (includes legacy)"""
    
    if any(chart.timing is not None for chart in song.charts.values()):
        raise ValueError(f"memon:{version} cannot represent a song with per-chart timing")

    if song.global_timing is None:
        raise ValueError("The song has no timing information")
    
    number_of_timing_events = len(song.global_timing.events)
    if number_of_timing_events != 1:
        if number_of_timing_events == 0:
            raise ValueError("The song has no BPM")
        else:
            raise ValueError(f"memon:{version} does not handle Stops or BPM changes")
    
    event = song.global_timing.events[0]
    if not isinstance(event, BPMChange):
        raise ValueError("The song file has no BPM")
    
    if event.BPM <= 0:
        raise ValueError("memon:legacy only accepts strictly positive BPMs")

    if event.time != 0:
        raise ValueError("memon:legacy only accepts a BPM on the first beat")
    
    for difficulty, chart in song.charts.items():
        if len(set(chart.notes)) != len(chart.notes):
            raise ValueError(f"{difficulty} chart has duplicate notes, these cannot be represented")


def _dump_to_json(memon: dict) -> IO:
    memon_fp = BytesIO()
    json.dump(memon, memon_fp, use_decimal=True, indent=4)
    return memon_fp


def _compute_resolution(notes: List[Union[TapNote, LongNote]]) -> int:
    return lcm(
        *chain(
            iter(note.time.denominator for note in notes),
            iter(note.duration.denominator for note in notes if isinstance(note, LongNote))
        )
    )


def _iter_dump_notes_v0(resolution: int, notes: List[Union[TapNote, LongNote]]) -> Iterable[Dict[str, int]]:
    for note in sorted(set(notes), key=lambda n: (n.time, n.position)):
        memon_note = {
            "n": note.index,
            "t": note.time.numerator * (resolution // note.time.denominator),
            "l": 0,
            "p": 0
        }
        if isinstance(note, LongNote):
            memon_note["l"] = note.duration.numerator * (resolution // note.duration.denominator)
            memon_note["p"] = _long_note_tail_value_v0(note)
        
        yield memon_note


def dump_memon_legacy(song: Song) -> Iterable[Tuple[Any, IO]]:
    
    check_representable_in_v0(song, "legacy")

    # JSON object preparation
    memon = {
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "jacket path": str(song.metadata.cover),
            "BPM": song.global_timing.events[0].BPM,
            "offset": song.global_timing.beat_zero_offset
        },
        "data": []
    }
    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"].append({
            "dif_name": difficulty,
            "level": chart.level,
            "resolution": resolution,
            "notes": list(_iter_dump_notes_v0(resolution, chart.notes))
        })

    return [(song, _dump_to_json(memon))]


def dump_memon_0_1_0(song: Song, folder: Path) -> None:
    
    check_representable_in_v0(song, "legacy")

    # JSON object preparation
    memon = {
        "version": "0.1.0",
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "album cover path": str(song.metadata.cover),
            "BPM": song.global_timing.events[0].BPM,
            "offset": song.global_timing.beat_zero_offset
        },
        "data": {}
    }
    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"][difficulty] = {
            "level": chart.level,
            "resolution": resolution,
            "notes": list(_iter_dump_notes_v0(resolution, chart.notes))
        }

    return [(song, _dump_to_json(memon))]


def dump_memon_0_2_0(song: Song, folder: Path) -> None:
    
    check_representable_in_v0(song, "legacy")

    # JSON object preparation
    memon = {
        "version": "0.2.0",
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "album cover path": str(song.metadata.cover),
            "BPM": song.global_timing.events[0].BPM,
            "offset": song.global_timing.beat_zero_offset,
            "preview" : {
                "position": song.metadata.preview_start,
                "length": song.metadata.preview_length,
            }
        },
        "data": {}
    }
    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"][difficulty] = {
            "level": chart.level,
            "resolution": resolution,
            "notes": list(_iter_dump_notes_v0(resolution, chart.notes))
        }
    
    return [(song, _dump_to_json(memon))]