from __future__ import annotations

from enum import Enum
from fractions import Fraction
from typing import List, Union
from io import StringIO
from dataclasses import dataclass
from functools import singledispatch
import ctypes
import warnings
from typing import Dict, Tuple
from pathlib import Path

from more_itertools import numeric_range

from jubeatools import song
from jubeatools.formats.filetypes import ChartFile
from jubeatools.formats.adapters import make_dumper_from_chart_file_dumper

from .timemap import TimeMap

AnyNote = Union[song.TapNote, song.LongNote]


class Command(Enum):
    END = 1
    MEASURE = 2
    HAKU = 3
    PLAY = 4
    LONG = 5
    TEMPO = 6


@dataclass(order=True)
class Event:
    """Represents a line in an .eve file"""

    time: int
    command: Command
    value: int

    def dump(self) -> str:
        return f"{self.time:>8},{self.command.name:<8},{self.value:>8}"


DIRECTION_TO_VALUE = {
    song.Direction.DOWN: 0,
    song.Direction.UP: 1,
    song.Direction.RIGHT: 2,
    song.Direction.LEFT: 3,
}

VALUE_TO_DIRECTION = {v: k for k, v in DIRECTION_TO_VALUE.items()}


def _dump_eve(song: song.Song, **kwargs: dict) -> List[ChartFile]:
    res = []
    for dif, chart, timing in song.iter_charts_with_timing():
        chart_text = dump_chart(chart.notes, timing)
        chart_bytes = chart_text.encode('ascii')
        res.append(ChartFile(chart_bytes, song, dif, chart))

    return res

dump_eve = make_dumper_from_chart_file_dumper(
    internal_dumper=_dump_eve,
    file_name_template=Path("{difficulty_index}.eve")
)


def dump_chart(notes: List[AnyNote], timing: song.Timing) -> str:
    time_map = TimeMap.from_timing(timing)
    note_events = make_note_events(notes, time_map)
    timing_events = make_timing_events(notes, timing, time_map)
    sorted_events = sorted(note_events + timing_events)
    return "\n".join(e.dump() for e in sorted_events)


def make_note_events(notes: List[AnyNote], time_map: TimeMap) -> List[Event]:
    return [make_note_event(note, time_map) for note in notes]


@singledispatch
def make_note_event(note: AnyNote, time_map: TimeMap) -> Event:
    raise NotImplementedError(f"Note of unknown type : {note}")


@make_note_event.register
def make_tap_note_event(note: song.TapNote, time_map: TimeMap) -> Event:
    ticks = ticks_at_beat(note.time, time_map)
    value = note.position.index
    return Event(time=ticks, command=Command.PLAY, value=value)


@make_note_event.register
def make_long_note_event(note: song.LongNote, time_map: TimeMap) -> Event:
    if not note.has_straight_tail():
        raise ValueError("Diagonal tails cannot be represented in eve format")

    duration = duration_in_ticks(note, time_map)
    direction = DIRECTION_TO_VALUE[note.tail_direction()]
    length = len(list(note.positions_covered())) - 1
    if not (1 <= length <= 3):
        raise ValueError(
            f"Given note has a length of {length}, which is not representable "
            "in the eve format"
        )
    position_index = note.position.index
    long_note_value = duration << 8 + length << 6 + direction << 4 + position_index
    ticks = ticks_at_beat(note.time, time_map)
    return Event(time=ticks, command=Command.LONG, value=long_note_value)


def make_timing_events(
    notes: List[AnyNote], timing: song.Timing, time_map: TimeMap
) -> List[Event]:
    bpm_events = [make_bpm_event(e, time_map) for e in timing.events]
    end_beat = choose_end_beat(notes)
    end_event = make_end_event(end_beat, time_map)
    measure_events = make_measure_events(end_beat, time_map)
    beat_events = make_beat_events(end_beat, time_map)
    return bpm_events + measure_events + beat_events + [end_event]


def make_bpm_event(bpm_change: song.BPMEvent, time_map: TimeMap) -> Event:
    ticks = ticks_at_beat(bpm_change.time, time_map)
    bpm_value = round(60 * 10 ** 6 / Fraction(bpm_change.BPM))
    return Event(time=ticks, command=Command.TEMPO, value=bpm_value)


def choose_end_beat(notes: List[AnyNote]) -> song.BeatsTime:
    """Leave 2 empty measures (4 beats) after the last event"""
    last_note_beat = compute_last_note_beat(notes)
    measure = last_note_beat - (last_note_beat % 4)
    return measure + song.BeatsTime(2 * 4)


def compute_last_note_beat(notes: List[AnyNote]) -> song.BeatsTime:
    """Returns the last beat at which a note event happens, either a tap note,
    the start of a long note or the end of a long note.

    If we don't take long notes ends into account we might end up with a long
    note end happening after the END tag which will cause jubeat to freeze when
    trying to render the note density graph"""
    note_times = set(n.time for n in notes)
    long_note_ends = set(
        n.time + n.duration for n in notes if isinstance(n, song.LongNote)
    )
    all_note_times = note_times | long_note_ends
    return max(all_note_times)


def make_end_event(end_beat: song.BeatsTime, time_map: TimeMap) -> Event:
    ticks = ticks_at_beat(end_beat, time_map)
    return Event(time=ticks, command=Command.END, value=0)


def make_measure_events(end_beat: song.BeatsTime, time_map: TimeMap) -> List[Event]:
    start = song.BeatsTime(0)
    stop = end_beat + song.BeatsTime(1)
    step = song.BeatsTime(4)
    beats = numeric_range(start, stop, step)
    return [make_measure_event(beat, time_map) for beat in beats]


def make_measure_event(beat: song.BeatsTime, time_map: TimeMap) -> Event:
    ticks = ticks_at_beat(beat, time_map)
    return Event(time=ticks, command=Command.MEASURE, value=0)


def make_beat_events(end_beat: song.BeatsTime, time_map: TimeMap) -> List[Event]:
    start = song.BeatsTime(0)
    stop = end_beat + song.BeatsTime(1, 2)
    step = song.BeatsTime(1)
    beats = numeric_range(start, stop, step)
    return [make_beat_event(beat, time_map) for beat in beats]


def make_beat_event(beat: song.BeatsTime, time_map: TimeMap) -> Event:
    ticks = ticks_at_beat(beat, time_map)
    return Event(time=ticks, command=Command.HAKU, value=0)

def load_eve(path: Path) -> song.Song:
    ...



def ticks_at_beat(time: song.BeatsTime, time_map: TimeMap) -> int:
    seconds_time = time_map.fractional_seconds_at(time)
    return seconds_to_ticks(seconds_time)


def duration_in_ticks(long: song.LongNote, time_map: TimeMap) -> int:
    press_time = time_map.fractional_seconds_at(long.time)
    release_time = time_map.fractional_seconds_at(long.time + long.duration)
    length_in_seconds = release_time - press_time
    return seconds_to_ticks(length_in_seconds)


def ticks_to_seconds(tick: int) -> Fraction:
    """Convert eve ticks (300 Hz) to seconds"""
    return Fraction(tick, 300)


def seconds_to_ticks(time: Fraction) -> int:
    """Convert fractional seconds to eve ticks (300 Hz)"""
    return round(time * 300)
