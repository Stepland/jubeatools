from collections import ChainMap, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from io import StringIO
from itertools import chain
from typing import Dict, Iterator, List, Optional, Tuple

from more_itertools import collapse, intersperse, mark_ends, windowed
from path import Path
from sortedcontainers import SortedDict, SortedKeyList, SortedSet

from jubeatools import __version__
from jubeatools.formats.filetypes import ChartFile, JubeatFile
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

from ..command import dump_command
from ..symbols import CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS

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
]

BEATS_TIME_TO_SYMBOL = {
    BeatsTime(1, 4) * index: symbol for index, symbol in enumerate(NOTE_SYMBOLS)
}

BEATS_TIME_TO_CIRCLE_FREE = {
    BeatsTime(1, 4) * index: symbol for index, symbol in enumerate(CIRCLE_FREE_SYMBOLS)
}

DIRECTION_TO_ARROW = {
    NotePosition(-1, 0): "＞",  # U+FF1E : FULLWIDTH GREATER-THAN SIGN
    NotePosition(1, 0): "＜",  # U+FF1C : FULLWIDTH LESS-THAN SIGN
    NotePosition(0, -1): "∨",  # U+2228 : LOGICAL OR
    NotePosition(0, 1): "∧",  # U+2227 : LOGICAL AND
}

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


def fraction_to_decimal(frac: Fraction):
    "Thanks stackoverflow ! https://stackoverflow.com/a/40468867/10768117"
    return frac.numerator / Decimal(frac.denominator)


@dataclass
class MonoColumnDumpedSection:
    current_beat: BeatsTime
    commands: Dict[str, Optional[str]] = field(default_factory=dict)
    symbol_definitions: Dict[BeatsTime, str] = field(default_factory=dict)
    symbols: Dict[BeatsTime, str] = field(default_factory=dict)
    notes: List[TapNote] = field(default_factory=list)

    def render(self, circle_free: bool = False) -> str:
        blocs = []
        commands = list(self._dump_commands())
        if commands:
            blocs.append(commands)
        symbols = list(self._dump_symbol_definitions())
        if symbols:
            blocs.append(symbols)
        notes = list(self._dump_notes(circle_free))
        if notes:
            blocs.append(notes)
        return "\n".join(collapse([intersperse("", blocs), "--"]))

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

    def _dump_notes(self, circle_free: bool = False,) -> Iterator[str]:
        frames: List[Dict[NotePosition, str]] = []
        frame: Dict[NotePosition, str] = {}
        for note in self.notes:
            if isinstance(note, LongNote):
                needed_positions = set(note.positions_covered())
                if needed_positions & frame.keys():
                    frames.append(frame)
                    frame = {}

                direction = note.tail_direction()
                arrow = DIRECTION_TO_ARROW[direction]
                line = DIRECTION_TO_LINE[direction]
                for is_first, is_last, pos in mark_ends(note.positions_covered()):
                    if is_first:
                        time_in_section = note.time - self.current_beat
                        symbol = self.symbols[time_in_section]
                        frame[pos] = symbol
                    elif is_last:
                        frame[pos] = arrow
                    else:
                        frame[pos] = line
            elif isinstance(note, TapNote):
                if note.position in frame:
                    frames.append(frame)
                    frame = {}
                time_in_section = note.time - self.current_beat
                symbol = self.symbols[time_in_section]
                frame[note.position] = symbol
            elif isinstance(note, LongNoteEnd):
                if note.position in frame:
                    frames.append(frame)
                    frame = {}
                time_in_section = note.time - self.current_beat
                if circle_free:
                    symbol = CIRCLE_FREE_SYMBOLS[time_in_section]
                else:
                    symbol = self.symbols[time_in_section]
                frame[note.position] = symbol

        frames.append(frame)
        dumped_frames = map(self._dump_frame, frames)
        yield from collapse(intersperse("", dumped_frames))

    @staticmethod
    def _dump_frame(frame: Dict[NotePosition, str]) -> Iterator[str]:
        for y in range(4):
            yield "".join(frame.get(NotePosition(x, y), "□") for x in range(4))


class Sections(SortedDict):

    """Custom SortedDict that also acts as a defaultdict of
    MonoColumnDumpedSection"""

    def add_section(self, beat):
        if beat not in self:
            section = MonoColumnDumpedSection(beat)
            self.__setitem__(beat, section)

    def __missing__(self, beat):
        section = MonoColumnDumpedSection(beat)
        self.__setitem__(beat, section)
        return section


@dataclass(frozen=True)
class LongNoteEnd:
    time: BeatsTime
    position: NotePosition


def _raise_if_unfit_for_mono_column(
    chart: Chart, timing: Timing, circle_free: bool = False
):
    if len(timing.events) < 1:
        raise ValueError("No BPM found in file") from None

    first_bpm = min(timing.events, key=lambda e: e.time)
    if first_bpm.time != 0:
        raise ValueError("First BPM event does not happen on beat zero")

    if any(
        not note.tail_is_straight()
        for note in chart.notes
        if isinstance(note, LongNote)
    ):
        raise ValueError(
            "Chart contains diagonal long notes, reprensenting these in"
            " mono_column format is not supported by jubeatools"
        )

    if circle_free and any(
        (note.time + note.duration) % BeatsTime(1, 4) != 0
        for note in chart.notes
        if isinstance(note, LongNote)
    ):
        raise ValueError(
            "Chart contains long notes whose ending timing aren't"
            " representable in #circlefree mode"
        )


def _dump_mono_column_chart(
    difficulty: str,
    chart: Chart,
    metadata: Metadata,
    timing: Timing,
    circle_free: bool = False,
) -> StringIO:

    _raise_if_unfit_for_mono_column(chart, timing, circle_free)

    timing_events = sorted(timing.events, key=lambda e: e.time)
    notes = SortedKeyList(set(chart.notes), key=lambda n: n.time)

    for note in chart.notes:
        if isinstance(note, LongNote):
            notes.add(LongNoteEnd(note.time + note.duration, note.position))

    all_events = SortedKeyList(timing_events + notes, key=lambda n: n.time)
    last_event = all_events[-1]
    last_measure = last_event.time // 4
    sections = Sections()
    for i in range(last_measure + 1):
        beat = BeatsTime(4) * i
        sections.add_section(beat)

    header = sections[0].commands
    header["o"] = int(timing.beat_zero_offset * 1000)
    header["lev"] = int(chart.level)
    header["dif"] = DIFFICULTIES.get(difficulty, 1)
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

    # Potentially create sub-sections for bpm changes
    for event in timing_events:
        sections[event.time].commands["t"] = event.BPM

    # First, Set every single b=… value
    for key, next_key in windowed(chain(sections.keys(), [None]), 2):
        if next_key is None:
            sections[key].commands["b"] = 4
        else:
            sections[key].commands["b"] = fraction_to_decimal(next_key - key)

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

    # Define extra symbols
    existing_symbols = deepcopy(BEATS_TIME_TO_SYMBOL)
    extra_symbols = iter(DEFAULT_EXTRA_SYMBOLS)
    for section_start, section in sections.items():
        # intentionally not a copy : at the end of this loop every section
        # holds a reference to a dict containing every defined symbol
        section.symbols = existing_symbols
        for note in section.notes:
            time_in_section = note.time - section_start
            if time_in_section not in existing_symbols:
                new_symbol = next(extra_symbols)
                section.symbol_definitions[time_in_section] = new_symbol
                existing_symbols[time_in_section] = new_symbol

    # Actual output to file
    file = StringIO()
    file.write(f"// Converted using jubeatools {__version__}\n")
    file.write(f"// https://github.com/Stepland/jubeatools\n\n")
    for section_start, section in sections.items():
        file.write(section.render(circle_free) + "\n")

    return file


def _dump_mono_column_internal(
    song: Song, circle_free: bool = False
) -> List[JubeatFile]:
    files = []
    for difficulty, chart in song.charts.items():
        contents = _dump_mono_column_chart(
            difficulty,
            chart,
            song.metadata,
            chart.timing or song.global_timing,
            circle_free,
        )
        files.append(ChartFile(contents, song, difficulty, chart))

    return files


def dump_mono_column(
    song: Song, circle_free: bool, folder: Path, name_pattern: str = None
):
    if not folder.isdir():
        raise ValueError(f"{folder} is not a directory")
