from collections import ChainMap, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from functools import partial
from io import StringIO
from itertools import chain, zip_longest
from math import ceil
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple, Union, cast

from more_itertools import chunked, collapse, intersperse, mark_ends, windowed
from sortedcontainers import SortedKeyList

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
from jubeatools.version import __version__

from ..command import dump_command
from ..dump_tools import (
    BEATS_TIME_TO_SYMBOL,
    COMMAND_ORDER,
    DEFAULT_EXTRA_SYMBOLS,
    DIRECTION_TO_ARROW,
    DIRECTION_TO_LINE,
    NOTE_TO_CIRCLE_FREE_SYMBOL,
    JubeatAnalyserDumpedSection,
    LongNoteEnd,
    SortedDefaultDict,
    create_sections_from_chart,
    fraction_to_decimal,
    jubeat_analyser_file_dumper,
)
from ..symbols import CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS

AnyNote = Union[TapNote, LongNote, LongNoteEnd]

EMPTY_BEAT_SYMBOL = "−"  # U+02212 : MINUS SIGN
EMPTY_POSITION_SYMBOL = "□"  # U+025A1 : WHITE SQUARE


@dataclass
class Frame:
    positions: Dict[NotePosition, str] = field(default_factory=dict)
    bars: Dict[int, Dict[int, str]] = field(default_factory=dict)

    def dump(self, length: Decimal) -> Iterator[str]:
        # Check that bars are contiguous
        for a, b in windowed(sorted(self.bars), 2):
            if b is not None and a is not None and b - a != 1:
                raise ValueError("Frame has discontinuous bars")
        # Check all bars are in the same 4-bar group
        if self.bars.keys() != set(bar % 4 for bar in self.bars):
            raise ValueError("Frame contains bars from different 4-bar groups")

        for pos, bar in zip_longest(self.dump_positions(), self.dump_bars(length)):
            if bar is None:
                bar = ""
            yield f"{pos} {bar}"

    def dump_positions(self) -> Iterator[str]:
        for y in range(4):
            yield "".join(
                self.positions.get(NotePosition(x, y), EMPTY_POSITION_SYMBOL)
                for x in range(4)
            )

    def dump_bars(self, length: Decimal) -> Iterator[str]:
        all_bars = []
        for i in range(ceil(length * 4)):
            bar_index = i // 4
            time_index = i % 4
            symbol = self.bars.get(bar_index, {}).get(time_index, EMPTY_BEAT_SYMBOL)
            all_bars.append(symbol)

        for i, bar in enumerate(chunked(all_bars, 4)):
            if i in self.bars:
                yield f"|{''.join(bar)}|"
            else:
                yield ""


class MemoDumpedSection(JubeatAnalyserDumpedSection):
    def render(self, circle_free: bool) -> str:
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
        return "\n".join(collapse(intersperse("", blocs)))

    def _dump_notes(self, circle_free: bool) -> Iterator[str]:
        notes_by_bar: Dict[int, List[AnyNote]] = defaultdict(list)
        bars: Dict[int, Dict[int, str]] = defaultdict(dict)
        chosen_symbols: Dict[BeatsTime, str] = {}
        symbols_iterator = iter(NOTE_SYMBOLS)
        for note in self.notes:
            time_in_section = note.time - self.current_beat
            bar_index = int(time_in_section)
            notes_by_bar[bar_index].append(note)
            if time_in_section % Fraction(1, 4) == 0:
                time_in_bar = time_in_section % Fraction(1)
                time_index = int(time_in_bar * 4)
                if time_index not in bars[bar_index]:
                    symbol = next(symbols_iterator)
                    chosen_symbols[time_in_section] = symbol
                    bars[bar_index][time_index] = symbol
            elif time_in_section not in self.symbols:
                raise ValueError(
                    f"No symbol defined for time in section : {time_in_section}"
                )

        # Create frame by bar
        section_symbols = ChainMap(chosen_symbols, self.symbols)
        frames_by_bar: Dict[int, List[Frame]] = defaultdict(list)
        for bar_index in range(ceil(self.length)):
            bar = bars.get(bar_index, {})
            frame = Frame()
            frame.bars[bar_index] = bar
            for note in notes_by_bar[bar_index]:
                time_in_section = note.time - self.current_beat
                symbol = section_symbols[time_in_section]
                if isinstance(note, TapNote):
                    if note.position in frame.positions:
                        frames_by_bar[bar_index].append(frame)
                        frame = Frame()
                    frame.positions[note.position] = symbol
                elif isinstance(note, LongNote):
                    needed_positions = set(note.positions_covered())
                    if needed_positions & frame.positions.keys():
                        frames_by_bar[bar_index].append(frame)
                        frame = Frame()
                    direction = note.tail_direction()
                    arrow = DIRECTION_TO_ARROW[direction]
                    line = DIRECTION_TO_LINE[direction]
                    for is_first, is_last, pos in mark_ends(note.positions_covered()):
                        if is_first:
                            frame.positions[pos] = symbol
                        elif is_last:
                            frame.positions[pos] = arrow
                        else:
                            frame.positions[pos] = line
                elif isinstance(note, LongNoteEnd):
                    if note.position in frame.positions:
                        frames_by_bar[bar_index].append(frame)
                        frame = Frame()
                    if circle_free and symbol in NOTE_TO_CIRCLE_FREE_SYMBOL:
                        symbol = NOTE_TO_CIRCLE_FREE_SYMBOL[symbol]
                    frame.positions[note.position] = symbol
            frames_by_bar[bar_index].append(frame)

        # Merge bar-specific frames is possible
        final_frames: List[Frame] = []
        for bar_index in range(ceil(self.length)):
            frames = frames_by_bar[bar_index]
            # Merge if :
            #  - No split in current bar (only one frame)
            #  - There is a previous frame
            #  - The previous frame is not a split frame (it holds a bar)
            #  - The previous and current bars are all in the same 4-bar group
            #  - The note positions in the previous frame do not clash with the current frame
            if (
                len(frames) == 1
                and final_frames
                and final_frames[-1].bars
                and max(final_frames[-1].bars.keys()) // 4
                == min(frames[0].bars.keys()) // 4
                and (
                    not (final_frames[-1].positions.keys() & frames[0].positions.keys())
                )
            ):
                final_frames[-1].bars.update(frames[0].bars)
                final_frames[-1].positions.update(frames[0].positions)
            else:
                final_frames.extend(frames)

        dumped_frames = map(lambda f: f.dump(self.length), final_frames)
        yield from collapse(intersperse("", dumped_frames))


def _raise_if_unfit_for_memo(chart: Chart, timing: Timing, circle_free: bool) -> None:
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
            " memo format is not supported by jubeatools"
        )


def _dump_memo_chart(
    difficulty: str,
    chart: Chart,
    metadata: Metadata,
    timing: Timing,
    circle_free: bool,
) -> StringIO:

    _raise_if_unfit_for_memo(chart, timing, circle_free)

    sections = create_sections_from_chart(
        MemoDumpedSection, chart, difficulty, timing, metadata, circle_free
    )

    # Jubeat Analyser format command
    sections[BeatsTime(0)].commands["memo"] = None

    # Define extra symbols
    existing_symbols: Dict[BeatsTime, str] = {}
    extra_symbols = iter(DEFAULT_EXTRA_SYMBOLS)
    for section_start, section in sections.items():
        # intentionally not a copy : at the end of this loop every section
        # holds a reference to a dict containing every defined symbol
        section.symbols = existing_symbols
        for note in section.notes:
            time_in_section = note.time - section_start
            if (
                time_in_section % Fraction(1, 4) != 0
                and time_in_section not in existing_symbols
            ):
                new_symbol = next(extra_symbols)
                section.symbol_definitions[time_in_section] = new_symbol
                existing_symbols[time_in_section] = new_symbol

    # Actual output to file
    file = StringIO()
    file.write(f"// Converted using jubeatools {__version__}\n")
    file.write(f"// https://github.com/Stepland/jubeatools\n\n")
    for _, section in sections.items():
        file.write(section.render(circle_free) + "\n\n")

    return file


def _dump_memo_internal(song: Song, circle_free: bool) -> List[ChartFile]:
    files: List[ChartFile] = []
    for difficulty, chart in song.charts.items():
        timing = chart.timing or song.global_timing
        assert timing is not None
        contents = _dump_memo_chart(
            difficulty, chart, song.metadata, timing, circle_free,
        )
        files.append(ChartFile(contents, song, difficulty, chart))

    return files


dump_memo = jubeat_analyser_file_dumper(_dump_memo_internal)
