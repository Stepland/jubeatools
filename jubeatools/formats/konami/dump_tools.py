import math
from fractions import Fraction
from functools import singledispatch
from typing import List

from more_itertools import numeric_range

from jubeatools import song
from jubeatools.formats.timemap import TimeMap

from .commons import AnyNote, Command, Event, bpm_to_value, ticks_at_beat


def make_events_from_chart(notes: List[AnyNote], timing: song.Timing) -> List[Event]:
    time_map = TimeMap.from_timing(timing)
    note_events = make_note_events(notes, time_map)
    timing_events = make_timing_events(notes, timing, time_map)
    return sorted(note_events + timing_events)


def make_note_events(notes: List[AnyNote], time_map: TimeMap) -> List[Event]:
    return [make_note_event(note, time_map) for note in notes]


@singledispatch
def make_note_event(note: AnyNote, time_map: TimeMap) -> Event:
    raise NotImplementedError(f"Unknown note type : {type(note)}")


@make_note_event.register
def make_tap_note_event(note: song.TapNote, time_map: TimeMap) -> Event:
    return Event.from_tap_note(note, time_map)


@make_note_event.register
def make_long_note_event(note: song.LongNote, time_map: TimeMap) -> Event:
    return Event.from_long_note(note, time_map)


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
    bpm_value = math.floor(bpm_to_value(Fraction(bpm_change.BPM)))
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
    return max(all_note_times, default=song.BeatsTime(0))


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
