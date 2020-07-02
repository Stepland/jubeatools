"""
Provides the Song class, the central model for chartsets
Every input format is converted to a Song instance
Every output format is created from a Song instance

Precision-critical times are stored as a fraction of beats,
otherwise a decimal number of seconds can be used
"""

from collections import UserList, namedtuple
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from functools import wraps
from typing import Iterator, List, Mapping, Optional, Type, Union

from multidict import MultiDict
from path import Path

BeatsTime = Fraction
SecondsTime = Decimal


def beats_time_from_ticks(ticks: int, resolution: int) -> BeatsTime:
    if resolution < 1:
        raise ValueError(f"resolution cannot be negative : {resolution}")
    return BeatsTime(ticks, resolution)


def convert_other(f):
    @wraps(f)
    def wrapped(self, other):
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


@dataclass(frozen=True)
class NotePosition:
    x: int
    y: int

    def __iter__(self):
        yield self.x
        yield self.y

    @property
    def index(self):
        return self.x + 4 * self.y

    def as_tuple(self):
        return (self.x, self.y)

    @classmethod
    def from_index(cls: Type["NotePosition"], index: int) -> "NotePosition":
        if not (0 <= index < 16):
            raise ValueError(f"Note position index out of range : {index}")

        return cls(x=index % 4, y=index // 4)

    @convert_other
    def __lt__(self, other):
        return self.as_tuple() < other.as_tuple()

    @convert_other
    def __add__(self, other):
        return NotePosition(self.x + other.x, self.y + other.y)

    @convert_other
    def __sub__(self, other):
        return NotePosition(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class TapNote:
    time: BeatsTime
    position: NotePosition


@dataclass(frozen=True)
class LongNote:
    time: BeatsTime
    position: NotePosition
    duration: BeatsTime
    tail_tip: NotePosition

    def __hash__(self):
        return hash((self.time, self.position))

    def tail_is_straight(self) -> bool:
        return (self.position.x == self.tail_tip.x) or (
            self.position.y == self.tail_tip.y
        )

    def tail_direction(self) -> NotePosition:
        if not self.tail_is_straight():
            raise ValueError("Can't get tail direction when it's not straight")
        diff = self.tail_tip - self.position
        if diff.x == 0:
            diff.y //= abs(diff.y)
        else:
            diff.x //= abs(diff.x)
        return diff

    def positions_covered(self) -> Iterator[NotePosition]:
        direction = self.tail_direction()
        position = self.position
        while position != self.tail_tip:
            yield position
            position = position + direction


@dataclass
class BPMEvent:
    time: BeatsTime
    BPM: Decimal


@dataclass
class Timing:
    events: List[BPMEvent]
    beat_zero_offset: SecondsTime


@dataclass
class Chart:
    level: Decimal
    timing: Optional[Timing] = None
    notes: List[Union[TapNote, LongNote]] = field(default_factory=list)


@dataclass
class Metadata:
    title: str
    artist: str
    audio: Path
    cover: Path
    preview_start: SecondsTime = SecondsTime(0)
    preview_length: SecondsTime = SecondsTime(0)


@dataclass
class Song:

    """The abstract representation format for all jubeat chart sets.
    A Song is a set of charts with associated metadata"""

    metadata: Metadata
    charts: Mapping[str, Chart] = field(default_factory=MultiDict)
    global_timing: Optional[Timing] = None
