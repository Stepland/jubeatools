import warnings
from collections import ChainMap
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from functools import reduce
from itertools import chain, product, zip_longest
from typing import Dict, Iterator, List, Mapping, Optional, Set, Tuple, Union

import constraint
from more_itertools import collapse, mark_ends
from parsimonious import Grammar, NodeVisitor, ParseError
from path import Path

from jubeatools.song import (
    BeatsTime,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    SecondsTime,
    Song,
    TapNote,
    Timing,
)

from ..command import is_command, parse_command
from ..files import load_files
from ..load_tools import (
    CIRCLE_FREE_TO_DECIMAL_TIME,
    CIRCLE_FREE_TO_NOTE_SYMBOL,
    EMPTY_BEAT_SYMBOLS,
    LONG_ARROWS,
    LONG_DIRECTION,
    DoubleColumnChartLine,
    DoubleColumnFrame,
    JubeatAnalyserParser,
    UnfinishedLongNote,
    decimal_to_beats,
    find_long_note_candidates,
    is_double_column_chart_line,
    is_empty_line,
    is_simple_solution,
    long_note_solution_heuristic,
    parse_double_column_chart_line,
    pick_correct_long_note_candidates,
    split_double_byte_line,
)
from ..symbol_definition import is_symbol_definition, parse_symbol_definition
from ..symbols import CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS


class Memo1Frame(DoubleColumnFrame):
    @property
    def duration(self) -> Decimal:
        return Decimal(len(self.timing_part))


@dataclass
class Memo1LoadedSection:
    frames: List[Memo1Frame]
    length: Decimal
    tempo: Decimal

    def __str__(self):
        res = []
        if self.length != 4:
            res += [f"b={self.length}", ""]
        for _, is_last, frame in mark_ends(self.frames):
            res += [str(frame)]
            if not is_last:
                res += [""]
        return "\n".join(res)


class Memo1Parser(JubeatAnalyserParser):
    def __init__(self):
        super().__init__()
        self.frames: List[Memo1Frame] = []
        self.sections: List[Memo1LoadedSection] = []

    def do_memo(self):
        raise ValueError("This is not a memo file")

    def do_memo1(self):
        ...

    do_boogie = do_memo2 = do_memo

    def do_bpp(self, value):
        if self.sections or self.frames:
            raise ValueError("jubeatools does not handle changes of #bpp halfway")
        else:
            self._do_bpp(value)

    def append_chart_line(self, line: DoubleColumnChartLine):
        if len(line.position.encode("shift-jis-2004")) != 4 * self.bytes_per_panel:
            raise SyntaxError(
                f"Invalid chart line for #bpp={self.bytes_per_panel} : {line}"
            )
        if line.timing is not None and self.bytes_per_panel == 2:
            if len(line.timing.encode("shift-jis-2004")) % 2 != 0:
                raise SyntaxError(f"Invalid chart line for #bpp=2 : {line}")
        self.current_chart_lines.append(line)
        if len(self.current_chart_lines) == 4:
            self._push_frame()

    def _split_chart_line(self, line: str):
        if self.bytes_per_panel == 2:
            return split_double_byte_line(line)
        else:
            return list(line)

    def _frames_duration(self) -> Decimal:
        return sum(frame.duration for frame in self.frames)

    def _push_frame(self):
        position_part = [
            self._split_chart_line(memo_line.position)
            for memo_line in self.current_chart_lines
        ]
        timing_part = [
            self._split_chart_line(memo_line.timing)
            for memo_line in self.current_chart_lines
            if memo_line.timing is not None
        ]
        frame = Memo1Frame(position_part, timing_part)
        # if the current frame has some timing info
        if frame.duration > 0:
            # and the previous frames already cover enough beats
            if self._frames_duration() >= self.beats_per_section:
                # then the current frame starts a new section
                self._push_section()

        self.frames.append(frame)
        self.current_chart_lines = []

    def _push_section(self):
        self.sections.append(
            Memo1LoadedSection(
                frames=deepcopy(self.frames),
                length=self.beats_per_section,
                tempo=self.current_tempo,
            )
        )
        self.frames = []
        self.section_starting_beat += self.beats_per_section

    def finish_last_few_notes(self):
        """Call this once when the end of the file is reached,
        flushes the chart line and chart frame buffers to create the last chart
        section"""
        if self.current_chart_lines:
            if len(self.current_chart_lines) != 4:
                raise SyntaxError(
                    f"Unfinished chart frame when flushing : {self.current_chart_lines}"
                )
            self._push_frame()
        self._push_section()

    def load_line(self, raw_line: str):
        line = raw_line.strip()
        if is_command(line):
            command, value = parse_command(line)
            self.handle_command(command, value)
        elif is_empty_line(line) or self.is_short_line(line):
            return
        elif is_double_column_chart_line(line):
            memo_chart_line = parse_double_column_chart_line(line)
            self.append_chart_line(memo_chart_line)
        else:
            raise SyntaxError(f"not a valid memo1 file line : {line}")

    def notes(self) -> Iterator[Union[TapNote, LongNote]]:
        if self.hold_by_arrow:
            yield from self._iter_notes()
        else:
            yield from self._iter_notes_without_longs()

    def _iter_frames(
        self,
    ) -> Iterator[
        Tuple[Mapping[str, BeatsTime], Memo1Frame, Decimal, Memo1LoadedSection]
    ]:
        """iterate over tuples of
        currently_defined_symbols, frame, section_starting_beat, section"""
        local_symbols: Dict[str, Decimal] = {}
        section_starting_beat = Decimal(0)
        for section in self.sections:
            frame_starting_beat = Decimal(0)
            for i, frame in enumerate(section.frames):
                if frame.timing_part:
                    frame_starting_beat = sum(f.duration for f in section.frames[:i])
                    local_symbols = {
                        symbol: BeatsTime(symbol_index, len(bar))
                        + bar_index
                        + decimal_to_beats(frame_starting_beat)
                        for bar_index, bar in enumerate(frame.timing_part)
                        for symbol_index, symbol in enumerate(bar)
                        if symbol not in EMPTY_BEAT_SYMBOLS
                    }
                yield local_symbols, frame, section_starting_beat, section
            section_starting_beat += section.length

    def _iter_notes(self) -> Iterator[Union[TapNote, LongNote]]:
        unfinished_longs: Dict[NotePosition, UnfinishedLongNote] = {}
        for (
            currently_defined_symbols,
            frame,
            section_starting_beat,
            section,
        ) in self._iter_frames():
            should_skip: Set[NotePosition] = set()

            # 1/3 : look for ends to unfinished long notes
            for pos, unfinished_long in unfinished_longs.items():
                x, y = pos.as_tuple()
                symbol = frame.position_part[y][x]
                if self.circle_free and symbol in CIRCLE_FREE_SYMBOLS:
                    circled_symbol = CIRCLE_FREE_TO_NOTE_SYMBOL[symbol]
                    try:
                        symbol_time = currently_defined_symbols[circled_symbol]
                    except KeyError:
                        raise SyntaxError(
                            "Chart section positional part constains the circle free "
                            f"symbol '{symbol}' but the associated circled symbol "
                            f"'{circled_symbol}' could not be found in the timing part:\n"
                            f"{section}"
                        )
                else:
                    try:
                        symbol_time = currently_defined_symbols[symbol]
                    except KeyError:
                        continue

                should_skip.add(pos)
                note_time = decimal_to_beats(section_starting_beat) + symbol_time
                yield unfinished_long.ends_at(note_time)

            unfinished_longs = {
                k: unfinished_longs[k] for k in unfinished_longs.keys() - should_skip
            }

            # 2/3 : look for new long notes starting on this bloc
            arrow_to_note_candidates = find_long_note_candidates(
                frame.position_part, currently_defined_symbols.keys(), should_skip
            )
            if arrow_to_note_candidates:
                solution = pick_correct_long_note_candidates(
                    arrow_to_note_candidates, frame.position_part,
                )
                for arrow_pos, note_pos in solution.items():
                    should_skip.add(arrow_pos)
                    should_skip.add(note_pos)
                    symbol = frame.position_part[note_pos.y][note_pos.x]
                    symbol_time = currently_defined_symbols[symbol]
                    note_time = decimal_to_beats(section_starting_beat) + symbol_time
                    unfinished_longs[note_pos] = UnfinishedLongNote(
                        time=note_time, position=note_pos, tail_tip=arrow_pos
                    )

            # 3/3 : find regular notes
            for y, x in product(range(4), range(4)):
                position = NotePosition(x, y)
                if position in should_skip:
                    continue
                symbol = frame.position_part[y][x]
                try:
                    symbol_time = currently_defined_symbols[symbol]
                except KeyError:
                    continue
                note_time = decimal_to_beats(section_starting_beat) + symbol_time
                yield TapNote(note_time, position)

    def _iter_notes_without_longs(self) -> Iterator[TapNote]:
        for (
            currently_defined_symbols,
            frame,
            section_starting_beat,
            _,
        ) in self._iter_frames():
            # cross compare symbols with the position information
            for y, x in product(range(4), range(4)):
                symbol = frame.position_part[y][x]
                try:
                    symbol_time = currently_defined_symbols[symbol]
                except KeyError:
                    continue
                note_time = decimal_to_beats(section_starting_beat) + symbol_time
                position = NotePosition(x, y)
                yield TapNote(note_time, position)


def _load_memo1_file(lines: List[str]) -> Song:
    parser = Memo1Parser()
    for i, raw_line in enumerate(lines):
        try:
            parser.load_line(raw_line)
        except Exception as e:
            raise SyntaxError(
                f"Error while parsing memo line {i} :\n" f"{type(e).__name__}: {e}"
            ) from None

    parser.finish_last_few_notes()
    metadata = Metadata(
        title=parser.title,
        artist=parser.artist,
        audio=parser.music,
        cover=parser.jacket,
    )
    if parser.preview_start is not None:
        metadata.preview_start = SecondsTime(parser.preview_start) / 1000
        metadata.preview_length = SecondsTime(10)

    timing = Timing(
        events=parser.timing_events, beat_zero_offset=SecondsTime(parser.offset) / 1000
    )
    charts = {
        parser.difficulty: Chart(
            level=parser.level,
            timing=timing,
            notes=sorted(parser.notes(), key=lambda n: (n.time, n.position)),
        )
    }
    return Song(metadata=metadata, charts=charts)


def load_memo1(path: Path) -> Song:
    files = load_files(path)
    charts = [_load_memo1_file(lines) for _, lines in files.items()]
    return reduce(Song.merge, charts)
