from collections import ChainMap, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from io import StringIO
from itertools import chain
from typing import IO, Dict, Iterator, List, Optional, Tuple

from more_itertools import collapse, intersperse, mark_ends, windowed
from sortedcontainers import SortedDict, SortedKeyList, SortedSet

from jubeatools import __version__
from jubeatools.song import (BeatsTime, Chart, LongNote, Metadata,
                             NotePosition, Song, TapNote, Timing)

from ..command import dump_command
from .commons import NOTE_SYMBOLS, CIRCLE_FREE_SYMBOLS

COMMAND_ORDER = SortedSet(
    ["b", "t", "m", "o", "r", "title", "artist", "lev", "dif", "jacket", "prevpos"]
)

BEATS_TIME_TO_SYMBOL = {
    BeatsTime(1, 4) * index: symbol for index, symbol in enumerate(NOTE_SYMBOLS)
}

BEATS_TIME_TO_CIRCLE_FREE = {
    BeatsTime(1, 4) * index: symbol for index, symbol in enumerate(CIRCLE_FREE_SYMBOLS)
}

DIRECTION_TO_ARROW = {
    NotePosition(-1,  0): "＞",  # U+FF1E : FULLWIDTH GREATER-THAN SIGN
    NotePosition( 1,  0): "＜",  # U+FF1C : FULLWIDTH LESS-THAN SIGN
    NotePosition( 0, -1): "∨",  # U+2228 : LOGICAL OR
    NotePosition( 0,  1): "∧",  # U+2227 : LOGICAL AND
}

DIRECTION_TO_LINE = {
    NotePosition(-1,  0): "―",  # U+2015 : HORIZONTAL BAR
    NotePosition( 1,  0): "―",
    NotePosition( 0, -1): "｜",  # U+FF5C : FULLWIDTH VERTICAL LINE
    NotePosition( 0,  1): "｜",
}


def fraction_to_decimal(frac: Fraction):
    "Thanks stackoverflow ! https://stackoverflow.com/a/40468867/10768117"
    return frac.numerator / Decimal(frac.denominator)


@dataclass
class MonoColumnDumpedSection:
    commands: Dict[str, Optional[str]] = field(default_factory=dict)
    symbol_definitions: Dict[BeatsTime, str] = field(default_factory=dict)
    notes: List[TapNote] = field(default_factory=list)

    def render(
        self,
        current_beat: BeatsTime,
        extra_symbols: Dict[BeatsTime, str],
        circle_free: bool = False
    ) -> str:
        blocs = []
        commands = list(self._dump_commands())
        if commands:
            blocs.append(commands)
        symbols = list(self._dump_symbol_definitions())
        if symbols:
            blocs.append(symbols)
        notes = list(self._dump_notes(current_beat, extra_symbols, circle_free))
        if notes:
            blocs.append(notes)
        return "\n".join(collapse([intersperse("", blocs), "--"]))

    def _dump_commands(self) -> Iterator[str]:
        keys = chain(COMMAND_ORDER, self.commands.keys() - COMMAND_ORDER)
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

    def _dump_notes(
        self,
        current_beat: BeatsTime,
        extra_symbols: Dict[BeatsTime, str],
        circle_free: bool = False
    ) -> Iterator[str]:
        frames: List[Dict[NotePosition, str]] = []
        frame: Dict[NotePosition, str] = {}
        symbols: Dict[BeatsTime, str] = ChainMap(
            extra_symbols, BEATS_TIME_TO_SYMBOL
        )
        for note in self.notes:
            if isinstance(note, LongNote):
                needed_positions = set(note.positions_covered())
                if needed_positions & frame.keys():
                    frames.append(frame)
                    frame = {}
                
                direction = note.tail_direction()
                arrow = DIRECTION_TO_ARROW[direction]
                line = DIRECTION_TO_LINE[direction]
                for is_first, is_last, pos in note.positions_covered():
                    if is_first:
                        time_in_section = note.time - current_beat
                        symbol = symbols[time_in_section]
                        frame[pos] = symbol
                    if is_last:
                        frame[pos] = arrow
                    else:
                        frame[pos] = line

            elif isinstance(note, TapNote):
                if note.position in frame:
                    frames.append(frame)
                    frame = {}
                time_in_section = note.time - current_beat
                symbol = symbols[time_in_section]
                frame[note.position] = symbol

            elif isinstance(note, LongNoteEnd):
                if note.position in frame:
                    frames.append(frame)
                    frame = {}
                time_in_section = note.time - current_beat
                if circle_free:
                    symbol = CIRCLE_FREE_SYMBOLS[time_in_section]
                else:
                    symbol = symbols[time_in_section]
                frame[note.position] = symbol

        frames.append(frame)
        dumped_frames = map(self._dump_frame, frames)
        yield from collapse(intersperse("", dumped_frames))


    @staticmethod
    def _dump_frame(frame: Dict[NotePosition, str]) -> Iterator[str]:
        for y in range(4):
            yield "".join(frame.get(NotePosition(x, y), "□") for x in range(4))


DIFFICULTIES = {"BSC": 1, "ADV": 2, "EXT": 3}

# I put a FUCKTON of extra characters just in case some insane chart uses
# loads of unusual beat divisions
DEFAULT_EXTRA_SYMBOLS = (
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
)

def _raise_if_unfit_for_mono_column(chart: Chart, timing: Timing, circle_free: bool = False):
    if len(timing.events) < 1:
        raise ValueError("No BPM found in file") from None

    first_bpm = min(timing.events, key=lambda e: e.time)
    if first_bpm.time != 0:
        raise ValueError("First BPM event does not happen on beat zero")
    
    if any(not note.tail_is_straight() for note in chart.notes if isinstance(note, LongNote)):
        raise ValueError(
            "Chart contains diagonal long notes, reprensenting these in"
            " mono_column format is not supported by jubeatools"
        )
    
    if circle_free and any(
        (note.time + note.duration) % BeatsTime(1, 4) != 0
        for note in chart.notes if isinstance(note, LongNote)
    ):
        raise ValueError(
            "Chart contains long notes whose ending timing aren't"
            " representable in #circlefree mode"
        )

class SortedDefaultDict(SortedDict):
    def __init__(self, default_factory, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_factory = default_factory
    
    def __missing__(self, key):
        value = self.default_factory()
        self.__setitem__(key, value)
        return value

@dataclass(frozen=True)
class LongNoteEnd:
    time: BeatsTime
    position: NotePosition

def _dump_mono_column_chart(
    difficulty: str, chart: Chart, metadata: Metadata, timing: Timing
) -> StringIO:

    _raise_if_unfit_for_mono_column(chart, timing)

    timing_events = sorted(timing.events, key=lambda e: e.time)
    notes = SortedKeyList(set(chart.notes), key=lambda n: n.time)
    # Add long note ends
    for note in chart.notes:
        if isinstance(note, LongNote):
            notes.add(LongNoteEnd(note.time+note.duration, note.position))
    last_event_time = max(timing_events[-1].time, notes[-1].time)
    last_measure = last_event_time // 4
    sections = SortedDefaultDict(
        MonoColumnDumpedSection,
        {BeatsTime(4) * i: MonoColumnDumpedSection() for i in range(last_measure + 1)},
    )
    sections[0].commands.update(
        o=int(timing.beat_zero_offset * 1000),
        m=metadata.audio,
        title=metadata.title,
        artist=metadata.artist,
        lev=int(chart.level),
        dif=DIFFICULTIES.get(difficulty, 1),
        jacket=metadata.cover,
        prevpos=int(metadata.preview_start * 1000),
    )
    # Potentially create sub-sections for bpm changes
    for event in timing_events:
        sections[event.time].commands["t"] = event.BPM
    # First, Set every single b=... value
    for key, next_key in windowed(chain(sections.keys(),[None]), 2):
        if next_key is None:
            sections[key].commands["b"] = 4
        else:
            sections[key].commands["b"] = fraction_to_decimal(next_key - key)
    # Then, trim all the redundant b=...
    last_b = 4
    for section in sections.values():
        current_b = section.commands["b"]
        if current_b == last_b:
            del section.commands["b"]
        else:
            last_b = current_b
    # Fill sections with notes
    for key, next_key in windowed(chain(sections.keys(),[None]), 2):
        sections[key].notes = list(
            notes.irange_key(min_key=key, max_key=next_key, inclusive=(True, False))
        )
    # Define extra symbols
    existing_symbols = deepcopy(BEATS_TIME_TO_SYMBOL)
    extra_symbols = iter(DEFAULT_EXTRA_SYMBOLS)
    all_extra_symbols = {}
    for section_start, section in sections.items():
        for note in section.notes:
            time_in_section = note.time - section_start
            if time_in_section not in existing_symbols:
                new_symbol = next(extra_symbols)
                section.symbol_definitions[time_in_section] = new_symbol
                all_extra_symbols[time_in_section] = new_symbol
                existing_symbols[time_in_section] = new_symbol

    # Actual output to file
    file = StringIO()
    file.write(f"// Converted using jubeatools {__version__}\n")
    file.write(f"// https://github.com/Stepland/jubeatools\n\n")
    for section_start, section in sections.items():
        file.write(section.render(section_start, all_extra_symbols) + "\n")

    return file


def dump_mono_column(song: Song) -> Dict[str, IO]:
    files = {}
    for difname, chart in song.charts.items():
        filename = f"{song.metadata.title} [{difname}].txt"
        files[filename] = _dump_mono_column_chart(
            difname, chart, song.metadata, chart.timing or song.global_timing,
        )
    return files
