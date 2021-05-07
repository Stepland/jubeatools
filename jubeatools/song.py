"""
Provides the Song class, the central model for chartsets
Every input format is converted to a Song instance
Every output format is created from a Song instance

Most timing-related info is stored as beat fractions,
otherwise a decimal number of seconds is used
"""

from __future__ import annotations

from dataclasses import astuple, dataclass, field
from decimal import Decimal
from fractions import Fraction
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterator, List, Mapping, Optional, Type, Union, Tuple
from enum import Enum, auto

from multidict import MultiDict

BeatsTime = Fraction
SecondsTime = Decimal


def beats_time_from_ticks(ticks: int, resolution: int) -> BeatsTime:
    if resolution < 1:
        raise ValueError(f"resolution cannot be negative : {resolution}")
    return BeatsTime(ticks, resolution)


def convert_other(
    f: Callable[[NotePosition, NotePosition], NotePosition]
) -> Callable[[NotePosition, Any], NotePosition]:
    @wraps(f)
    def wrapped(self: NotePosition, other: Any) -> NotePosition:
        if isinstance(other, NotePosition):
            other_note = other
        else:
            try:
                other_note = NotePosition(*other)
            except Exception:
                raise ValueError(
                    f"Invalid type for {f.__name__} with NotePosition : {type(other).__name__}"
                )

        return f(self, other_note)

    return wrapped


@dataclass(frozen=True, order=True)
class NotePosition:
    """A specific square on the controller. (0, 0) is the top-left button, x
    goes right, y goes down.

        x →
        0 1 2 3
    y 0 □ □ □ □
    ↓ 1 □ □ □ □
      2 □ □ □ □
      3 □ □ □ □
    """

    x: int
    y: int

    def __iter__(self) -> Iterator[int]:
        yield from astuple(self)

    @property
    def index(self) -> int:
        return self.x + 4 * self.y

    @classmethod
    def from_index(cls, index: int) -> NotePosition:
        if not (0 <= index < 16):
            raise ValueError(f"Note position index out of range : {index}")

        return cls(x=index % 4, y=index // 4)

    @convert_other
    def __add__(self, other: NotePosition) -> NotePosition:
        return NotePosition(self.x + other.x, self.y + other.y)

    @convert_other
    def __sub__(self, other: NotePosition) -> NotePosition:
        return NotePosition(self.x - other.x, self.y - other.y)


@dataclass(frozen=True, unsafe_hash=True)
class TapNote:
    time: BeatsTime
    position: NotePosition


@dataclass(frozen=True, unsafe_hash=True)
class LongNote:
    time: BeatsTime
    position: NotePosition
    duration: BeatsTime
    # tail tip starting position as absolute position on the playfield
    tail_tip: NotePosition

    def has_straight_tail(self) -> bool:
        return (self.position.x == self.tail_tip.x) or (
            self.position.y == self.tail_tip.y
        )

    def tail_direction(self) -> Direction:
        """Direction in which the tail moves"""
        if not self.has_straight_tail():
            raise ValueError("Can't get tail direction when it's not straight")

        if self.tail_tip.x == self.position.x:
            if self.tail_tip.y > self.position.y:
                return Direction.UP
            else:
                return Direction.DOWN
        else:
            if self.tail_tip.x > self.position.x:
                return Direction.LEFT
            else:
                return Direction.RIGHT

    def positions_covered(self) -> Iterator[NotePosition]:
        direction = self.tail_direction()
        step = TAIL_DIRECTION_TO_NOTE_TO_TAIL_VECTOR[direction]
        position = self.position
        yield position
        while position != self.tail_tip:
            position = position + step
            yield position


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


TAIL_DIRECTION_TO_NOTE_TO_TAIL_VECTOR = {
    Direction.UP: NotePosition(0, 1),
    Direction.DOWN: NotePosition(0, -1),
    Direction.LEFT: NotePosition(1, 0),
    Direction.RIGHT: NotePosition(-1, 0),
}


@dataclass(frozen=True)
class BPMEvent:
    time: BeatsTime
    BPM: Decimal


@dataclass(unsafe_hash=True)
class Timing:
    events: List[BPMEvent]
    beat_zero_offset: SecondsTime


@dataclass
class Chart:
    level: Decimal
    timing: Optional[Timing] = None
    notes: List[Union[TapNote, LongNote]] = field(default_factory=list)


@dataclass
class Preview:
    start: SecondsTime
    length: SecondsTime


@dataclass
class Metadata:
    title: Optional[str] = None
    artist: Optional[str] = None
    audio: Optional[Path] = None
    cover: Optional[Path] = None
    preview: Optional[Preview] = None
    preview_file: Optional[Path] = None


class Difficulty(str, Enum):
    BASIC = "BSC"
    ADVANCED = "ADV"
    EXTREME = "EXT"


@dataclass
class Song:

    """The abstract representation format for all jubeat chart sets.
    A Song is a set of charts with associated metadata"""

    metadata: Metadata
    charts: Mapping[str, Chart] = field(default_factory=MultiDict)
    common_timing: Optional[Timing] = None

    def merge(self, other: "Song") -> "Song":
        if self.metadata != other.metadata:
            raise ValueError(
                "Merge conflit in song metadata :\n"
                f"{self.metadata}\n"
                f"{other.metadata}"
            )
        charts: MultiDict[Chart] = MultiDict()
        charts.extend(self.charts)
        charts.extend(other.charts)
        if (
            self.common_timing is not None
            and other.common_timing is not None
            and self.common_timing != other.common_timing
        ):
            raise ValueError("Can't merge songs with differing global timings")
        common_timing = self.common_timing or other.common_timing
        return Song(self.metadata, charts, common_timing)

    def iter_charts_with_timing(self) -> Iterator[Tuple[str, Chart, Timing]]:
        for dif, chart in self.charts.items():
            timing = chart.timing or self.common_timing
            if timing is None:
                raise ValueError(
                    f"Neither song nor {dif} chart have any timing information"
                )
            yield dif, chart, timing
