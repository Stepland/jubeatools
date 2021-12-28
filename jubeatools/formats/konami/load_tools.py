from decimal import Decimal
from typing import Iterable, List, Optional, Set

from more_itertools import numeric_range

from jubeatools import song
from jubeatools.formats.load_tools import round_beats
from jubeatools.formats.timemap import BPMAtSecond, TimeMap
from jubeatools.utils import group_by

from .commons import (
    VALUE_TO_DIRECTION,
    AnyNote,
    Command,
    EveLong,
    Event,
    ticks_to_seconds,
    value_to_truncated_bpm,
)


def make_chart_from_events(events: Iterable[Event], beat_snap: int = 240) -> song.Chart:
    events_by_command = group_by(events, lambda e: e.command)
    bpms = [
        BPMAtSecond(
            seconds=ticks_to_seconds(e.time), BPM=value_to_truncated_bpm(e.value)
        )
        for e in sorted(events_by_command[Command.TEMPO])
    ]
    time_map = TimeMap.from_seconds(bpms)
    tap_notes: List[AnyNote] = [
        make_tap_note(e.time, e.value, time_map, beat_snap)
        for e in events_by_command[Command.PLAY]
    ]
    long_notes: List[AnyNote] = [
        make_long_note(e.time, e.value, time_map, beat_snap)
        for e in events_by_command[Command.LONG]
    ]
    all_notes = sorted(tap_notes + long_notes, key=lambda n: (n.time, n.position))
    timing = time_map.convert_to_timing_info(beat_snap=beat_snap)
    end_tick = events_by_command[Command.END].pop().time
    hakus = make_hakus(
        [e.time for e in events_by_command[Command.HAKU]],
        end_tick,
        time_map,
        beat_snap,
    )
    return song.Chart(level=Decimal(0), timing=timing, notes=all_notes, hakus=hakus)


def make_tap_note(
    ticks: int, value: int, time_map: TimeMap, beat_snap: int
) -> song.TapNote:
    time = beats_at_tick(ticks, time_map, beat_snap)
    position = song.NotePosition.from_index(value)
    return song.TapNote(time=time, position=position)


def make_long_note(
    ticks: int, value: int, time_map: TimeMap, beat_snap: int
) -> song.LongNote:
    seconds = ticks_to_seconds(ticks)
    raw_beats = time_map.beats_at(seconds)
    beats = round_beats(raw_beats, beat_snap)
    eve_long = EveLong.from_value(value)
    seconds_duration = ticks_to_seconds(eve_long.duration)
    raw_beats_duration = time_map.beats_at(seconds + seconds_duration) - raw_beats
    beats_duration = round_beats(raw_beats_duration, beat_snap)
    position = song.NotePosition.from_index(eve_long.position)
    direction = VALUE_TO_DIRECTION[eve_long.direction]
    step_vector = song.TAIL_DIRECTION_TO_OUTWARDS_VECTOR[direction]
    raw_tail_pos = position + (eve_long.length * step_vector)
    tail_pos = song.NotePosition.from_raw_position(raw_tail_pos)
    return song.LongNote(
        time=beats, position=position, duration=beats_duration, tail_tip=tail_pos
    )


def make_hakus(
    hakus: List[int], end: int, time_map: TimeMap, beat_snap: int
) -> Optional[Set[song.BeatsTime]]:
    """Try to detect if the haku pattern is regular, in which case return None,
    otherwise return the parsed hakus"""
    roughly_rounded_hakus = make_raw_hakus(hakus, time_map, beat_snap=4)
    rough_end = beats_at_tick(end, time_map, beat_snap=4)
    if follows_regular_haku_pattern(roughly_rounded_hakus, rough_end):
        return None
    else:
        return make_raw_hakus(hakus, time_map, beat_snap)


def make_raw_hakus(
    hakus: List[int], time_map: TimeMap, beat_snap: int
) -> Set[song.BeatsTime]:
    return set(beats_at_tick(haku, time_map, beat_snap) for haku in hakus)


def follows_regular_haku_pattern(
    hakus: Set[song.BeatsTime], end_command: song.BeatsTime
) -> bool:
    """Regular hakus extend at least till the END command in a 4/4 rhythm"""
    if len(hakus) == 0:
        return False

    start = min(hakus)
    if (start % 1) != 0:
        return False

    haku_end = max(hakus)
    if (haku_end % 1) != 0:
        return False

    if haku_end < end_command:
        return False

    stop = haku_end + song.BeatsTime(1, 2)
    step = song.BeatsTime(1)
    regular = numeric_range(start, stop, step)
    return sorted(hakus) == list(regular)


def beats_at_tick(tick: int, time_map: TimeMap, beat_snap: int) -> song.BeatsTime:
    seconds = ticks_to_seconds(tick)
    raw_beats = time_map.beats_at(seconds)
    return round_beats(raw_beats, beat_snap)
