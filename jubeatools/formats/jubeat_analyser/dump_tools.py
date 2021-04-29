"""Collection of tools realted to dumping to jubeat analyser formats"""
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from itertools import chain
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Mapping,
    Optional,
    TypeVar,
    Union,
)

from more_itertools import collapse, intersperse, mark_ends, windowed
from sortedcontainers import SortedDict, SortedKeyList

from jubeatools.formats.filetypes import ChartFile
from jubeatools.formats.typing import Dumper
from jubeatools.song import (
    BeatsTime,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    Song,
    TapNote,
    Timing,
)

from .command import dump_command
from .symbols import CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS

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
    NotePosition(-1, 0): "＞",  # U+FF1E : FULLWIDTH GREATER-THAN SIGN
    NotePosition(1, 0): "＜",  # U+FF1C : FULLWIDTH LESS-THAN SIGN
    NotePosition(0, -1): "∨",  # U+2228 : LOGICAL OR
    NotePosition(0, 1): "∧",  # U+2227 : LOGICAL AND
}

# do NOT use the regular vertical bar, it will clash with the timing portion
DIRECTION_TO_LINE = {
    NotePosition(-1, 0): "―",  # U+2015 : HORIZONTAL BAR
    NotePosition(1, 0): "―",
    NotePosition(0, -1): "｜",  # U+FF5C : FULLWIDTH VERTICAL LINE
    NotePosition(0, 1): "｜",
}

DIFFICULTIES = {"BSC": 1, "ADV": 2, "EXT": 3}

# I put a FUCKTON of extra characters just in case some insane chart uses
# loads of unusual beat divisions
DEFAULT_EXTRA_SYMBOLS = (
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
)


def fraction_to_decimal(frac: Fraction) -> Decimal:
    "Thanks stackoverflow ! https://stackoverflow.com/a/40468867/10768117"
    return frac.numerator / Decimal(frac.denominator)


@dataclass(frozen=True)
class LongNoteEnd:
    time: BeatsTime
    position: NotePosition


K = TypeVar("K")
V = TypeVar("V")


class SortedDefaultDict(SortedDict, Generic[K, V]):

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


# Here we split dataclass and ABC stuff since mypy curently can't handle both
# at once on a single class definition
@dataclass
class _JubeatAnalyerDumpedSection:
    current_beat: BeatsTime
    length: Decimal = Decimal(4)
    commands: Dict[str, Optional[str]] = field(default_factory=dict)
    symbol_definitions: Dict[BeatsTime, str] = field(default_factory=dict)
    symbols: Dict[BeatsTime, str] = field(default_factory=dict)
    notes: List[Union[TapNote, LongNote, LongNoteEnd]] = field(default_factory=list)


class JubeatAnalyserDumpedSection(_JubeatAnalyerDumpedSection, ABC):
    def _dump_commands(self) -> Iterator[str]:
        keys = chain(COMMAND_ORDER, self.commands.keys() - set(COMMAND_ORDER))
        for key in keys:
            try:
                value = self.commands[key]
            except KeyError:
                continue
            yield dump_command(key, value)

    def _dump_symbol_definitions(self) -> Iterator[str]:
        for time, symbol in self.symbol_definitions.items():
            decimal_time = fraction_to_decimal(time)
            yield f"*{symbol}:{decimal_time:.6f}"

    @abstractmethod
    def _dump_notes(self, circle_free: bool) -> Iterator[str]:
        ...


S = TypeVar("S", bound=JubeatAnalyserDumpedSection)


def create_sections_from_chart(
    section_factory: Callable[[BeatsTime], S],
    chart: Chart,
    difficulty: str,
    timing: Timing,
    metadata: Metadata,
    circle_free: bool,
) -> Mapping[BeatsTime, S]:
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
    header["lev"] = int(chart.level)
    header["dif"] = DIFFICULTIES.get(difficulty, 3)
    if metadata.audio:
        header["m"] = metadata.audio
    if metadata.title:
        header["title"] = metadata.title
    if metadata.artist:
        header["artist"] = metadata.artist
    if metadata.cover:
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
        if next_key is None:
            length = Decimal(4)
        else:
            length = fraction_to_decimal(next_key - key)
        sections[key].commands["b"] = length
        sections[key].length = length

    # Then, trim all the redundant b=…
    last_b = 4
    for section in sections.values():
        current_b = section.commands["b"]
        if current_b == last_b:
            del section.commands["b"]
        else:
            last_b = current_b

    # Fill sections with notes
    for key, next_key in windowed(chain(sections.keys(), [None]), 2):
        sections[key].notes = list(
            notes.irange_key(min_key=key, max_key=next_key, inclusive=(True, False))
        )

    return sections


def jubeat_analyser_file_dumper(
    internal_dumper: Callable[[Song, bool], List[ChartFile]]
) -> Dumper:
    """Factory function to create a jubeat analyser file dumper from the internal dumper"""

    def dumper(
        song: Song, path: Path, *, circle_free: bool = False, **kwargs: Any
    ) -> Dict[Path, bytes]:
        files = internal_dumper(song, circle_free)
        res = {}
        if path.is_dir():
            title = song.metadata.title or "out"
            name_format = title + " {difficulty}{dedup_index}.txt"
        else:
            name_format = "{base}{dedup_index}{ext}"

        for chartfile in files:
            i = 0
            filepath = name_format.format(
                base=path.parent / path.stem,
                difficulty=DIFFICULTIES.get(chartfile.difficulty, chartfile.difficulty),
                dedup_index="" if i == 0 else f"-{i}",
                ext=path.suffix,
            )
            while filepath in res:
                i += 1
                filepath = name_format.format(
                    base=path.parent / path.stem,
                    difficulty=DIFFICULTIES.get(
                        chartfile.difficulty, chartfile.difficulty
                    ),
                    dedup_index="" if i == 0 else f"-{i}",
                    ext=path.suffix,
                )

            res[Path(filepath)] = chartfile.contents.getvalue().encode("shift-jis-2004")

        return res

    return dumper
