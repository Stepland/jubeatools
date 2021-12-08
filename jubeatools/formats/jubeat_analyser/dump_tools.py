"""Collection of tools related to dumping to jubeat analyser formats"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from itertools import chain
from pathlib import Path
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    Iterator,
    List,
    Mapping,
    TypedDict,
    TypeVar,
    Union,
)

from more_itertools import windowed
from sortedcontainers import SortedDict, SortedKeyList

from jubeatools.formats.dump_tools import (
    DIFFICULTY_NUMBER,
    make_dumper_from_chart_file_dumper,
)
from jubeatools.formats.filetypes import ChartFile
from jubeatools.formats.typing import Dumper
from jubeatools.song import (
    BeatsTime,
    Chart,
    Direction,
    LongNote,
    Metadata,
    NotePosition,
    Song,
    TapNote,
    Timing,
)
from jubeatools.utils import fraction_to_decimal

from .command import dump_command
from .symbols import CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS
from .typing import JubeatAnalyserChartDumper

COMMAND_ORDER = [
    "b",
    "t",
    "m",
    "o",
    "r",
    "title",
    "artist",
    "lev",
    "dif",
    "jacket",
    "prevpos",
    "holdbyarrow",
    "circlefree",
]

BEATS_TIME_TO_SYMBOL = {
    BeatsTime(1, 4) * index: symbol for index, symbol in enumerate(NOTE_SYMBOLS)
}

BEATS_TIME_TO_CIRCLE_FREE = {
    BeatsTime(1, 4) * index: symbol for index, symbol in enumerate(CIRCLE_FREE_SYMBOLS)
}

NOTE_TO_CIRCLE_FREE_SYMBOL = dict(zip(NOTE_SYMBOLS, CIRCLE_FREE_SYMBOLS))

DIRECTION_TO_ARROW = {
    Direction.RIGHT: "＞",  # U+FF1E : FULLWIDTH GREATER-THAN SIGN
    Direction.LEFT: "＜",  # U+FF1C : FULLWIDTH LESS-THAN SIGN
    Direction.DOWN: "∨",  # U+2228 : LOGICAL OR
    Direction.UP: "∧",  # U+2227 : LOGICAL AND
}

# do NOT use the regular vertical bar, it will clash with the timing portion
DIRECTION_TO_LINE = {
    Direction.RIGHT: "―",  # U+2015 : HORIZONTAL BAR
    Direction.LEFT: "―",
    Direction.UP: "｜",  # U+FF5C : FULLWIDTH VERTICAL LINE
    Direction.DOWN: "｜",
}

# I put a FUCKTON of extra characters just in case some insane chart uses
# loads of unusual beat divisions.
# /!\ The Vs are left out on purpose since they would be mistaken for
# long note arrows
DEFAULT_EXTRA_SYMBOLS = (
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｗｘｙｚ"
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
)


@dataclass(frozen=True)
class LongNoteEnd:
    time: BeatsTime
    position: NotePosition


K = TypeVar("K")
V = TypeVar("V")


class SortedDefaultDict(SortedDict, DefaultDict[K, V]):

    """Custom SortedDict that also acts as a defaultdict,
    passes the key to the value factory"""

    def __init__(self, factory: Callable[[K], V], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.__factory__ = factory

    def add_key(self, key: K) -> None:
        if key not in self:
            value = self.__factory__(key)
            self.__setitem__(key, value)

    def __missing__(self, key: K) -> V:
        value = self.__factory__(key)
        self.__setitem__(key, value)
        return value


class Commands(TypedDict, total=False):
    b: Union[int, Fraction, Decimal]
    t: Union[int, Fraction, Decimal]
    m: Union[str, Path]
    o: int
    r: int
    title: str
    artist: str
    lev: Union[int, Decimal]
    dif: int
    jacket: Union[str, Path]
    prevpos: int
    holdbyarrow: int
    circlefree: int
    memo: None
    memo1: None
    memo2: None
    boogie: None
    pw: int
    ph: int
    bpp: int


# Here we split dataclass and ABC stuff since mypy curently can't handle both
# at once on a single class definition
@dataclass
class _JubeatAnalyerDumpedSection:
    current_beat: BeatsTime
    length: BeatsTime = BeatsTime(4)
    commands: Commands = field(default_factory=Commands)  # type: ignore
    symbol_definitions: Dict[BeatsTime, str] = field(default_factory=dict)
    symbols: Dict[BeatsTime, str] = field(default_factory=dict)
    notes: List[Union[TapNote, LongNote, LongNoteEnd]] = field(default_factory=list)


class JubeatAnalyserDumpedSection(_JubeatAnalyerDumpedSection, ABC):
    def _dump_commands(self) -> Iterator[str]:
        keys = chain(COMMAND_ORDER, self.commands.keys() - set(COMMAND_ORDER))
        for key in keys:
            if key in self.commands:
                yield dump_command(key, self.commands[key])  # type: ignore

    def _dump_symbol_definitions(self) -> Iterator[str]:
        for time, symbol in self.symbol_definitions.items():
            decimal_time = fraction_to_decimal(time)
            yield f"*{symbol}:{decimal_time:.6}"

    @abstractmethod
    def _dump_notes(self, circle_free: bool) -> Iterator[str]:
        ...

    @abstractmethod
    def render(self, circle_free: bool) -> str:
        ...


def create_sections_from_chart(
    section_factory: Callable[[BeatsTime], JubeatAnalyserDumpedSection],
    chart: Chart,
    difficulty: str,
    timing: Timing,
    metadata: Metadata,
    circle_free: bool,
) -> Mapping[BeatsTime, JubeatAnalyserDumpedSection]:
    sections = SortedDefaultDict(section_factory)

    timing_events = sorted(timing.events, key=lambda e: e.time)
    notes = SortedKeyList(set(chart.notes), key=lambda n: n.time)

    for note in chart.notes:
        if isinstance(note, LongNote):
            notes.add(LongNoteEnd(note.time + note.duration, note.position))

    all_events = SortedKeyList(timing_events + notes, key=lambda n: n.time)
    last_event = all_events[-1]
    last_measure = last_event.time // 4
    for i in range(last_measure + 1):
        beat = BeatsTime(4) * i
        sections.add_key(beat)

    header = sections[BeatsTime(0)].commands
    header["o"] = int(timing.beat_zero_offset * 1000)
    header["lev"] = Decimal(chart.level)
    header["dif"] = DIFFICULTY_NUMBER.get(difficulty, 3)
    if metadata.audio is not None:
        header["m"] = metadata.audio
    if metadata.title is not None:
        header["title"] = metadata.title
    if metadata.artist is not None:
        header["artist"] = metadata.artist
    if metadata.cover is not None:
        header["jacket"] = metadata.cover
    if metadata.preview is not None:
        header["prevpos"] = int(metadata.preview.start * 1000)

    if any(isinstance(note, LongNote) for note in chart.notes):
        header["holdbyarrow"] = 1

    if circle_free:
        header["circlefree"] = 1

    # Potentially create sub-sections for bpm changes
    for event in timing_events:
        sections[event.time].commands["t"] = event.BPM

    # First, Set every single b=… value
    for key, next_key in windowed(chain(sections.keys(), [None]), 2):
        if key is None:
            continue
        elif next_key is None:
            length = BeatsTime(4)
        else:
            length = next_key - key

        sections[key].commands["b"] = length
        sections[key].length = length

    # Then, trim all the redundant b=…
    last_b: Union[int, Fraction, Decimal] = 4
    for section in sections.values():
        current_b = section.commands["b"]
        if current_b == last_b:
            del section.commands["b"]
        else:
            last_b = current_b

    # Fill sections with notes
    for key, next_key in windowed(chain(sections.keys(), [None]), 2):
        assert key is not None
        sections[key].notes = list(
            notes.irange_key(min_key=key, max_key=next_key, inclusive=(True, False))
        )

    return sections


def make_full_dumper_from_jubeat_analyser_chart_dumper(
    chart_dumper: JubeatAnalyserChartDumper,
) -> Dumper:
    """Factory function to create a fully fledged song dumper from
    the internal chart dumper of jubeat analyser formats"""

    def song_dumper(
        song: Song, *, circle_free: bool = False, **kwargs: Any
    ) -> List[ChartFile]:
        files: List[ChartFile] = []
        for difficulty, chart, timing in song.iter_charts_with_timing():
            chart_file = chart_dumper(
                difficulty,
                chart,
                song.metadata,
                timing,
                circle_free,
            )
            file_bytes = chart_file.getvalue().encode(
                "shift-jis-2004", errors="surrogateescape"
            )
            files.append(ChartFile(file_bytes, song, difficulty, chart))

        return files

    return make_dumper_from_chart_file_dumper(
        internal_dumper=song_dumper,
        file_name_template=Path("{title} {difficulty_number}.txt"),
    )
