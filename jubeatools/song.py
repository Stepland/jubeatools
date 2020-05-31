"""
Provides the Song class, the central model for chartsets
Every input format is converted to a Song instance
Every output format is created from a Song instance

Precision-critical times are stored as a fraction of beats,
otherwise a decimal number of seconds can be used
"""

from dataclasses import dataclass
from collections import namedtuple, UserList
from decimal import Decimal
from fractions import Fraction
from typing import List, Optional, Union, Mapping

from path import Path
from multidict import MultiDict


class BeatsTime(Fraction):
    ...


class SecondsTime(Decimal):
    ...


@dataclass
class NotePosition:
    x: int
    y: int

    @property
    def index(self):
        return self.x + 4*self.y


@dataclass
class TapNote:
    time: BeatsTime
    position: NotePosition


@dataclass
class LongNote:
    time: BeatsTime
    position: NotePosition
    duration: BeatsTime
    tail_tip: NotePosition

    def __hash__(self):
        return hash((self.time, self.position))


@dataclass
class BPMChange:
    time: BeatsTime
    BPM: Decimal


@dataclass
class Stop:
    time: BeatsTime
    duration: BeatsTime


@dataclass
class Timing:
    events: List[Union[BPMChange, Stop]]
    beat_zero_offset: SecondsTime


@dataclass
class Chart:
    level: Decimal
    timing: Optional[Timing]
    notes: List[Union[TapNote, LongNote]]


@dataclass
class Metadata:
    title: str
    artist: str
    audio: Path
    cover: Path
    preview_start: SecondsTime
    preview_length: SecondsTime


class Song:
    """
    The abstract representation format for all jubeat chart sets.
    A Song is a set of charts with associated metadata
    """
    def __init__(self):
        self.metadata = Metadata()
        self.charts : Mapping[str, Chart] = MultiDict()
        self.global_timing : Optional[Timing] = Timing()