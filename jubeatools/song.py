"""
Provides the Song class, the central model for chartsets
Every input format is converted to a Song instance
Every output format is created from a Song instance

Precision-critical times are stored as a fraction of beats,
otherwise a decimal number of seconds can be used
"""

from dataclasses import dataclass, field
from collections import namedtuple, UserList
from decimal import Decimal
from fractions import Fraction
from typing import List, Optional, Union, Mapping, Type

from path import Path
from multidict import MultiDict


class BeatsTime(Fraction):
    @classmethod
    def from_ticks(cls: Type[Fraction], ticks: int, resolution: int) -> "BeatsTime":
        if resolution < 1:
            raise ValueError(f"resolution cannot be negative : {resolution}")
        return cls(ticks, resolution)


class SecondsTime(Decimal):
    ...


@dataclass(frozen=True)
class NotePosition:
    x: int
    y: int

    @property
    def index(self):
        return self.x + 4 * self.y

    @classmethod
    def from_index(cls: Type["NotePosition"], index: int) -> "NotePosition":
        if not (0 <= index < 16):
            raise ValueError(f"Note position index out of range : {index}")

        return cls(x=index % 4, y=index // 4)


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
