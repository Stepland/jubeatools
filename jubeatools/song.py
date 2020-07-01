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
from typing import List, Mapping, Optional, Type, Union

from multidict import MultiDict
from path import Path

BeatsTime = Fraction
SecondsTime = Decimal


def beats_time_from_ticks(ticks: int, resolution: int) -> BeatsTime:
    if resolution < 1:
        raise ValueError(f"resolution cannot be negative : {resolution}")
    return BeatsTime(ticks, resolution)


@dataclass(frozen=True)
class NotePosition:
    x: int
    y: int

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
    
    def __lt__(self, other):
        if not isinstance(other, NotePosition):
            try:
                x, y = other
            except ValueError:
                raise ValueError(f"Cannot add NotePosition with {type(other).__name__}")
        else:
            x = other.x
            y = other.y

        return self.as_tuple() < (x, y)

    def __add__(self, other):
        if not isinstance(other, NotePosition):
            try:
                x, y = other
            except ValueError:
                raise ValueError(f"Cannot add NotePosition with {type(other).__name__}")
        else:
            x = other.x
            y = other.y

        return NotePosition(self.x+x, self.y+y)


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
