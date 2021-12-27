"""Provides the Song class, the central model for chartsets
Every input format is converted to a Song instance
Every output format is created from a Song instance

Most timing-related info is stored as beat fractions, otherwise a decimal
number of seconds is used"""

from __future__ import annotations

from collections import Counter
from dataclasses import Field, astuple, dataclass, field, fields
from decimal import Decimal
from enum import Enum, auto
from fractions import Fraction
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from multidict import MultiDict

from jubeatools.utils import none_or

BeatsTime = Fraction
SecondsTime = Decimal


def beats_time_from_ticks(ticks: int, resolution: int) -> BeatsTime:
    if resolution < 1:
        raise ValueError(f"resolution cannot be negative : {resolution}")
    return BeatsTime(ticks, resolution)


def convert_other(
    f: Callable[[Position, Position], Position]
) -> Callable[[Position, Any], Position]:
    @wraps(f)
    def wrapped(self: Position, other: Any) -> Position:
        if isinstance(other, Position):
            other_pos = other
        else:
            try:
                other_pos = Position(*other)
            except Exception:
                raise ValueError(f"Could not convert {type(other)} to a Position")

        return f(self, other_pos)

    return wrapped


@dataclass(frozen=True, order=True)
class Position:
    """2D integer vector"""

    x: int
    y: int

    def __iter__(self) -> Iterator[int]:
        yield from astuple(self)

    @convert_other
    def __add__(self, other: Position) -> Position:
        return Position(self.x + other.x, self.y + other.y)

    @convert_other
    def __sub__(self, other: Position) -> Position:
        return Position(self.x - other.x, self.y - other.y)

    def __mul__(self, other: int) -> Position:
        return Position(self.x * other, self.y * other)

    __rmul__ = __mul__


@dataclass(frozen=True, order=True)
class NotePosition(Position):
    """A specific square on the controller. (0, 0) is the top-left button, x
    goes right, y goes down.

        x →
        0 1 2 3
    y 0 □ □ □ □
    ↓ 1 □ □ □ □
      2 □ □ □ □
      3 □ □ □ □

    The main difference with Position is that x and y MUST be between 0 and 3
    """

    def __post_init__(self) -> None:
        if not 0 <= self.x < 4:
            raise ValueError("x out of [0, 3] range")
        if not 0 <= self.y < 4:
            raise ValueError("y out of [0, 3] range")

    @property
    def index(self) -> int:
        return self.x + 4 * self.y

    @classmethod
    def from_index(cls, index: int) -> NotePosition:
        if not (0 <= index < 16):
            raise ValueError(f"Note position index out of range : {index}")

        return cls(x=index % 4, y=index // 4)

    @classmethod
    def from_raw_position(cls, pos: Position) -> NotePosition:
        return cls(x=pos.x, y=pos.y)


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
            raise ValueError("Can't get cardinal direction of diagonal long note")

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
        step = TAIL_DIRECTION_TO_OUTWARDS_VECTOR[direction]
        position = self.position
        yield position
        while position != self.tail_tip:
            position = NotePosition.from_raw_position(position + step)
            yield position


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


TAIL_DIRECTION_TO_OUTWARDS_VECTOR = {
    Direction.UP: Position(0, 1),
    Direction.DOWN: Position(0, -1),
    Direction.LEFT: Position(1, 0),
    Direction.RIGHT: Position(-1, 0),
}


@dataclass(frozen=True)
class BPMEvent:
    time: BeatsTime
    BPM: Decimal


@dataclass(unsafe_hash=True)
class Timing:
    events: Sequence[BPMEvent]
    beat_zero_offset: SecondsTime

    def __post_init__(self) -> None:
        self.events = tuple(self.events)


@dataclass
class Chart:
    level: Optional[Decimal]
    timing: Optional[Timing] = None
    hakus: Optional[Set[BeatsTime]] = None
    notes: List[Union[TapNote, LongNote]] = field(default_factory=list)


@dataclass(frozen=True)
class Preview:
    """Frozen so it can be hashed to be deduped using a set when merging
    Metadata instances"""

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

    @classmethod
    def permissive_merge(cls, *metadatas: "Metadata") -> "Metadata":
        """Make the "sum" of all the given metadata instances, if possible. If
        several instances have different defined values for the same field,
        merging will fail. Fields with Noneor empty values (empty string or
        empty path) are conscidered undefined and their values can be replaced
        by an actual value if supplied by at least one object from the given
        iterable."""
        return cls(
            **{f.name: _get_common_value(f, metadatas) for f in fields(cls)},
        )


def _get_common_value(field_: Field, metadatas: Iterable[Metadata]) -> Any:
    raw_values = []
    empty_values = []
    for m in metadatas:
        value = getattr(m, field_.name)
        if value is None:
            continue
        elif not value:
            empty_values.append(value)
        else:
            raw_values.append(value)

    real_values = set(raw_values)
    if len(real_values) > 1:
        raise ValueError(
            f"Can't merge metadata, the {field_.name} field has "
            f"conflicting possible values : {real_values}"
        )

    try:
        return real_values.pop()
    except KeyError:
        pass

    try:
        return empty_values.pop()
    except IndexError:
        pass

    return None


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
    common_hakus: Optional[Set[BeatsTime]] = None

    @classmethod
    def from_monochart_instances(cls, *songs: "Song") -> "Song":
        metadata = Metadata.permissive_merge(*(song.metadata for song in songs))
        charts: MultiDict[Chart] = MultiDict()
        for song in songs:
            song.remove_common_timing()
            song.remove_common_hakus()
            charts.extend(song.charts)

        merged = cls(
            metadata=metadata,
            charts=charts,
        )
        merged.minimize_timings()
        merged.minimize_hakus()
        return merged

    def minimize_timings(self) -> None:
        """Turn timings into minimal form : Use the most common timing object
        as the common timing, if it is used by more than two charts, otherwise
        each chart gets its own timing object and no common timing is defined"""
        self.remove_common_timing()
        counts = Counter(c.timing for c in self.charts.values())
        ((most_used, count),) = counts.most_common(1)
        if count >= 2:
            self.common_timing = most_used
            for chart in self.charts.values():
                if chart.timing == most_used:
                    chart.timing = None

    def remove_common_timing(self) -> None:
        """Modify the song object so that no chart relies on the common timing
        object, charts that previously did rely on it now have a chart-specific
        timing object equal to the old common timing"""
        for _, chart, applicable_timing in self.iter_charts_with_applicable_timing():
            chart.timing = applicable_timing

        self.common_timing = None

    def minimize_hakus(self) -> None:
        """Same deal as "minimize_timings" but with hakus"""
        self.remove_common_hakus()
        counts = Counter(
            none_or(frozenset.__call__, c.hakus) for c in self.charts.values()
        )
        most_used, count = counts.most_common(1).pop()
        if count >= 2:
            self.common_hakus = most_used
            for chart in self.charts.values():
                if chart.hakus == most_used:
                    chart.hakus = None

    def remove_common_hakus(self) -> None:
        for chart in self.charts.values():
            if chart.hakus is None:
                chart.hakus = self.common_hakus

        self.common_hakus = None

    def iter_charts_with_applicable_timing(self) -> Iterator[Tuple[str, Chart, Timing]]:
        for dif, chart in self.charts.items():
            timing = chart.timing or self.common_timing
            if timing is None:
                raise ValueError(
                    f"Neither song nor {dif} chart have any timing information"
                )
            yield dif, chart, timing
