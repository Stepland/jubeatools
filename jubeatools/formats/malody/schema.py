from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Tuple, Union

from marshmallow.validate import Range
from marshmallow_dataclass import NewType, class_schema


class Ordered:
    class Meta:
        ordered = True


@dataclass
class SongInfo(Ordered):
    title: Optional[str]
    artist: Optional[str]
    id: Optional[int]


class Mode(int, Enum):
    KEY = 0  # Vertical Scrolling Rhythm Game
    # 1 : Unused
    # 2 : Unused
    CATCH = 3  # EZ2CATCH / Catch the Beat
    PAD = 4  # Jubeat
    TAIKO = 5  # Taiko no Tatsujin
    RING = 6  # Reminds me of Beatstream ?


@dataclass
class Metadata(Ordered):
    cover: Optional[str]  # path to album art ?
    creator: Optional[str]  # Chart author
    background: Optional[str]  # path to background image
    version: Optional[str]  # freeform difficulty name
    id: Optional[int]
    mode: int
    time: Optional[int]  # creation timestamp ?
    song: SongInfo


PositiveInt = NewType("PositiveInt", int, validate=Range(min=0))
BeatTime = Tuple[PositiveInt, PositiveInt, PositiveInt]
StrictlyPositiveDecimal = NewType(
    "StrictlyPositiveDecimal", Decimal, validate=Range(min=0, min_inclusive=False)
)


@dataclass
class BPMEvent(Ordered):
    beat: BeatTime
    bpm: StrictlyPositiveDecimal


ButtonIndex = NewType("ButtonIndex", int, validate=Range(min=0, max=15))


@dataclass
class TapNote(Ordered):
    beat: BeatTime
    index: ButtonIndex


@dataclass
class LongNote(Ordered):
    beat: BeatTime
    index: ButtonIndex
    endbeat: BeatTime
    endindex: ButtonIndex


@dataclass
class Sound(Ordered):
    """Used both for the background music and keysounds"""

    beat: BeatTime
    sound: str  # audio file path
    type: int
    offset: int
    isBgm: Optional[bool]
    vol: Optional[int]  # Volume, out of 100
    x: Optional[int]


# TODO: find a keysounded chart to discovery the other values
class SoundType(int, Enum):
    BACKGROUND_MUSIC = 1


Event = Union[Sound, LongNote, TapNote]


@dataclass
class Chart(Ordered):
    meta: Metadata
    time: List[BPMEvent] = field(default_factory=list)
    note: List[Event] = field(default_factory=list)


CHART_SCHEMA = class_schema(Chart)()
