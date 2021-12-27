from dataclasses import astuple, dataclass, field
from decimal import Decimal
from functools import partial
from typing import Any, Dict, List, Optional, Tuple, Union

from marshmallow import EXCLUDE, Schema, ValidationError, post_dump, validate
from marshmallow_dataclass import NewType, class_schema

PositiveDecimal = NewType("PositiveDecimal", Decimal, validate=validate.Range(min=0))
StrictlyPositiveDecimal = NewType(
    "StrictlyPositiveDecimal",
    Decimal,
    validate=validate.Range(min=0, min_inclusive=False),
)


@dataclass
class PreviewSample:
    start: PositiveDecimal
    duration: StrictlyPositiveDecimal


Preview = Union[str, PreviewSample]


@dataclass
class Metadata:
    title: Optional[str]
    artist: Optional[str]
    audio: Optional[str]
    jacket: Optional[str]
    preview: Optional[Preview]


PositiveInt = NewType("PositiveInt", int, validate=validate.Range(min=0))
StrictlyPositiveInt = NewType(
    "StrictlyPositiveInteger", int, validate=validate.Range(min=0, min_inclusive=False)
)
MixedNumber = Tuple[int, int, int]
SymbolicTime = Union[int, MixedNumber]


def validate_symbolic_time(t: SymbolicTime) -> None:
    if isinstance(t, int):
        if t < 0:
            raise ValidationError("Negative ticks are not allowed")
    elif isinstance(t, tuple):
        validate_mixed_number(t)


def validate_mixed_number(m: MixedNumber) -> None:
    if m[0] < 0:
        raise ValidationError("First number in fraction tuple can't be negative")
    elif m[1] < 0:
        raise ValidationError("Second number in fraction tuple can't be negative")
    elif m[2] < 1:
        raise ValidationError("Third number in fraction tuple can't be less than 1")


def validate_strictly_positive_mixed_number(m: MixedNumber) -> None:
    if (m[0], m[1]) == (0, 0):
        raise ValidationError("The tuple must represent a strictly positive number")


@dataclass
class BPMEvent:
    beat: SymbolicTime = field(metadata={"validate": validate_symbolic_time})
    bpm: StrictlyPositiveDecimal


@dataclass
class Timing:
    offset: Optional[Decimal]
    resolution: Optional[StrictlyPositiveInt]
    bpms: Optional[List[BPMEvent]]
    hakus: Optional[List[SymbolicTime]] = field(
        metadata={"validate": partial(map, validate_symbolic_time)}
    )

    def remove_default_values(self) -> "Timing":
        return self.remove_common_values(DEFAULT_TIMING)

    def remove_common_values(self, other: "Timing") -> "Timing":
        return Timing(
            offset=None if self.offset == other.offset else self.offset,
            resolution=None if self.resolution == other.resolution else self.resolution,
            bpms=None if self.bpms == other.bpms else self.bpms,
            hakus=None if self.hakus == other.hakus else self.hakus,
        )

    def __bool__(self) -> bool:
        return any(f is not None for f in astuple(self))

    @classmethod
    def fill_in_defaults(cls, *timings: Optional["Timing"]) -> "Timing":
        ordered = [*timings, DEFAULT_TIMING]
        return cls.merge(*(t for t in ordered if t is not None))

    @classmethod
    def merge(cls, *timings: "Timing") -> "Timing":
        offset = next((t.offset for t in timings if t.offset is not None), None)
        resolution = next(
            (t.resolution for t in timings if t.resolution is not None), None
        )
        bpms = next((t.bpms for t in timings if t.bpms is not None), None)
        hakus = next((t.hakus for t in timings if t.hakus is not None), None)
        return cls(
            offset=offset,
            resolution=resolution,
            bpms=bpms,
            hakus=hakus,
        )


DEFAULT_TIMING = Timing(
    offset=Decimal(0),
    resolution=240,
    bpms=[BPMEvent(0, Decimal(120))],
    hakus=None,
)

Button = NewType("Button", int, validate=validate.Range(min=0, max=15))


@dataclass
class TapNote:
    n: Button
    t: SymbolicTime = field(metadata={"validate": validate_symbolic_time})


def validate_symbolic_duration(t: SymbolicTime) -> None:
    if isinstance(t, int):
        if t < 1:
            raise ValidationError("Duration has to be positive and non-zero")
    elif isinstance(t, tuple):
        validate_mixed_number(t)
        validate_strictly_positive_mixed_number(t)


TailIn6Notation = NewType("TailIn6Notation", int, validate=validate.Range(min=0, max=5))


@dataclass
class LongNote(TapNote):
    l: SymbolicTime = field(metadata={"validate": validate_symbolic_duration})
    p: TailIn6Notation


# LongNote first otherwise long notes get interpreted as tap notes
Note = Union[LongNote, TapNote]


@dataclass
class Chart:
    level: Optional[Decimal]
    resolution: Optional[StrictlyPositiveInt]
    timing: Optional[Timing]
    notes: List[Note]


Version = NewType("Version", str, validate=validate.Equal("1.0.0"))


@dataclass
class File:
    version: Version
    metadata: Optional[Metadata]
    timing: Optional[Timing]
    data: Dict[str, Chart]


class BaseSchema(Schema):
    class Meta:
        ordered = True
        unknown = EXCLUDE

    @post_dump
    def _remove_none_values(self, data: dict, **kwargs: Any) -> dict:
        return remove_none_values(data)


def remove_none_values(data: dict) -> dict:
    return {key: value for key, value in data.items() if value is not None}


FILE_SCHEMA = class_schema(File, base_schema=BaseSchema)()
