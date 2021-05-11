from decimal import Decimal
from functools import reduce
from pathlib import Path
from typing import Any, Iterator, List, Optional

from jubeatools import song
from jubeatools.formats.load_tools import make_folder_loader, round_beats
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
from .timemap import BPMAtSecond, TimeMap


def load_eve(path: Path, *, beat_snap: int = 240, **kwargs: Any) -> song.Song:
    files = load_folder(path)
    charts = [_load_eve(l, p, beat_snap=beat_snap) for p, l in files.items()]
    return reduce(song.Song.merge, charts)


def load_file(path: Path) -> List[str]:
    return path.read_text(encoding="ascii").split("\n")


load_folder = make_folder_loader("*.eve", load_file)


def _load_eve(lines: List[str], file_path: Path, *, beat_snap: int = 240) -> song.Song:
    events = list(iter_events(lines))
    events_by_command = group_by(events, lambda e: e.command)
    bpms = [
        BPMAtSecond(
            seconds=ticks_to_seconds(e.time), BPM=value_to_truncated_bpm(e.value)
        )
        for e in sorted(events_by_command[Command.TEMPO])
    ]
    time_map = TimeMap.from_seconds(bpms)
    tap_notes: List[AnyNote] = [
        make_tap_note(e.time, e.value, time_map)
        for e in events_by_command[Command.PLAY]
    ]
    long_notes: List[AnyNote] = [
        make_long_notes(e.time, e.value, time_map)
        for e in events_by_command[Command.LONG]
    ]
    all_notes = sorted(tap_notes + long_notes, key=lambda n: (n.time, n.position))
    timing = time_map.convert_to_timing_info(beat_snap=beat_snap)
    chart = song.Chart(level=Decimal(0), timing=timing, notes=all_notes)
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


def make_tap_note(ticks: int, value: int, time_map: TimeMap) -> song.TapNote:
    seconds = ticks_to_seconds(ticks)
    raw_beats = time_map.beats_at(seconds)
    beats = round_beats(raw_beats)
    position = song.NotePosition.from_index(value)
    return song.TapNote(time=beats, position=position)


def make_long_notes(ticks: int, value: int, time_map: TimeMap) -> song.LongNote:
    seconds = ticks_to_seconds(ticks)
    raw_beats = time_map.beats_at(seconds)
    beats = round_beats(raw_beats)
    eve_long = EveLong.from_value(value)
    seconds_duration = ticks_to_seconds(eve_long.duration)
    raw_beats_duration = time_map.beats_at(seconds + seconds_duration) - raw_beats
    beats_duration = round_beats(raw_beats_duration)
    position = song.NotePosition.from_index(eve_long.position)
    direction = VALUE_TO_DIRECTION[eve_long.direction]
    step_vector = song.TAIL_DIRECTION_TO_OUTWARDS_VECTOR[direction]
    raw_tail_pos = position + (eve_long.length * step_vector)
    tail_pos = song.NotePosition.from_raw_position(raw_tail_pos)
    return song.LongNote(
        time=beats, position=position, duration=beats_duration, tail_tip=tail_pos
    )


def guess_difficulty(filename: str) -> Optional[song.Difficulty]:
    try:
        return song.Difficulty(filename.upper())
    except ValueError:
        return None
