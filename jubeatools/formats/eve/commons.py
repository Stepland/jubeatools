from __future__ import annotations

from dataclasses import astuple, dataclass
from enum import Enum
from fractions import Fraction
from typing import Union

from jubeatools import song

from .timemap import TimeMap

AnyNote = Union[song.TapNote, song.LongNote]

DIRECTION_TO_VALUE = {
    song.Direction.DOWN: 0,
    song.Direction.UP: 1,
    song.Direction.RIGHT: 2,
    song.Direction.LEFT: 3,
}

VALUE_TO_DIRECTION = {v: k for k, v in DIRECTION_TO_VALUE.items()}

# int is here to allow sorting
class Command(int, Enum):
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

    def __post_init__(self) -> None:
        try:
            check_func = VALUES_CHECKERS[self.command]
        except KeyError:
            # most likely no check function associated : forget about it
            pass

        try:
            check_func(self.value)
        except ValueError as e:
            raise ValueError(
                f"{self.value} is not a valid value for the {self.command!r} "
                f"command. {e}"
            )

    def dump(self) -> str:
        return f"{self.time:>8},{self.command.name:<8},{self.value:>8}"

    @classmethod
    def from_tap_note(cls, note: song.TapNote, time_map: TimeMap) -> Event:
        ticks = ticks_at_beat(note.time, time_map)
        value = note.position.index
        return Event(time=ticks, command=Command.PLAY, value=value)

    @classmethod
    def from_long_note(cls, note: song.LongNote, time_map: TimeMap) -> Event:
        if not note.has_straight_tail():
            raise ValueError("Diagonal tails cannot be represented in eve format")

        eve_long = EveLong(
            duration=duration_in_ticks(note, time_map),
            length=len(list(note.positions_covered())) - 1,
            direction=DIRECTION_TO_VALUE[note.tail_direction()],
            position=note.position.index,
        )
        ticks = ticks_at_beat(note.time, time_map)
        return Event(time=ticks, command=Command.LONG, value=eve_long.value)


def is_zero(value: int) -> None:
    if value != 0:
        raise ValueError(f"Value should be zero")


def is_valid_button_index(value: int) -> None:
    # Should raise ValueError if invalid
    _ = song.NotePosition.from_index(value)


def is_valid_tail_position(value: int) -> None:
    # Should raise ValueError if invalid
    _ = EveLong.from_value(value)


def is_not_zero(value: int) -> None:
    if value == 0:
        raise ValueError(f"Value cannot be zero")


VALUES_CHECKERS = {
    Command.END: is_zero,
    Command.MEASURE: is_zero,
    Command.HAKU: is_zero,
    Command.PLAY: is_valid_button_index,
    Command.LONG: is_valid_tail_position,
    Command.TEMPO: is_not_zero,
}


@dataclass
class EveLong:
    duration: int
    length: int
    direction: int
    position: int

    def __post_init__(self) -> None:
        if self.duration < 0:
            raise ValueError("Duration can't be negative")
        if not 1 <= self.length < 4:
            raise ValueError("Tail length must be between 1 and 3 inclusive")
        if not 0 <= self.position < 16:
            raise ValueError("Note Position must be between 0 and 15 inclusive")
        if not 0 <= self.direction < 4:
            raise ValueError("direction value must be between 0 and 3 inclusive")

        pos = song.NotePosition.from_index(self.position)
        direction = VALUE_TO_DIRECTION[self.direction]
        step_vector = song.TAIL_DIRECTION_TO_OUTWARDS_VECTOR[direction]
        tail_pos = pos + (self.length * step_vector)
        if not ((0 <= tail_pos.x < 4) and (0 <= tail_pos.y < 4)):
            raise ValueError(
                f"Long note tail starts on {astuple(tail_pos)} which is "
                "outside the screen"
            )

    @classmethod
    def from_value(cls, value: int) -> EveLong:
        if value < 0:
            raise ValueError("Value cannot be negative")

        position = value & 0b1111  # first 4 bits
        direction = (value >> 4) & 0b11  # next 2 bits
        length = (value >> 6) & 0b11  # next 2 bits
        duration = value >> 8  # remaining bits
        return cls(duration, length, direction, position)

    @property
    def value(self) -> int:
        return (
            self.duration << 8 + self.length << 6 + self.direction << 4 + self.position
        )


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
