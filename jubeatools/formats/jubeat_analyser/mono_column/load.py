import re
import warnings
from collections import Counter
from copy import deepcopy
from dataclasses import astuple, dataclass
from decimal import Decimal
from enum import Enum
from functools import reduce
from itertools import product
from typing import Dict, Iterator, List, Set, Tuple

import constraint
from parsimonious import Grammar, NodeVisitor, ParseError
from path import Path

from jubeatools.song import (
    BeatsTime,
    BPMEvent,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    SecondsTime,
    Song,
    TapNote,
    Timing,
    Union,
)

from ..command import is_command, parse_command
from ..files import load_files
from ..load_tools import (
    CIRCLE_FREE_TO_DECIMAL_TIME,
    LONG_ARROWS,
    LONG_DIRECTION,
    JubeatAnalyserParser,
    UnfinishedLongNote,
    decimal_to_beats,
    find_long_note_candidates,
    is_empty_line,
    is_simple_solution,
    long_note_solution_heuristic,
    pick_correct_long_note_candidates,
    split_double_byte_line,
)
from ..symbol_definition import is_symbol_definition, parse_symbol_definition
from ..symbols import CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS

mono_column_chart_line_grammar = Grammar(
    r"""
    line            = ws chart_line ws comment?
    chart_line      = ~r"[^*#:|\-/\s]{4,8}"
    ws              = ~r"[\t ]*"
    comment         = ~r"//.*"
"""
)


class MonoColumnChartLineVisitor(NodeVisitor):
    def visit_line(self, node, visited_children):
        _, chart_line, _, _ = node.children
        return chart_line.text

    def generic_visit(self, node, visited_children):
        ...


def is_mono_column_chart_line(line: str) -> bool:
    try:
        mono_column_chart_line_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_mono_column_chart_line(line: str) -> str:
    return MonoColumnChartLineVisitor().visit(
        mono_column_chart_line_grammar.parse(line)
    )


SEPARATOR = re.compile(r"--.*")


def is_separator(line: str) -> bool:
    return bool(SEPARATOR.match(line))


SYMBOL_TO_DECIMAL_TIME = {
    symbol: Decimal("0.25") * index for index, symbol in enumerate(NOTE_SYMBOLS)
}


@dataclass
class MonoColumnLoadedSection:
    """
    An intermediate reprensetation of what's parsed from a mono-column
    chart section, contains :
    - raw chart lines
    - defined timing symbols
    - length in beats (usually 4)
    - tempo
    """

    chart_lines: List[str]
    symbols: Dict[str, Decimal]
    length: Decimal
    tempo: Decimal

    def blocs(self, bpp=2) -> Iterator[List[List[str]]]:
        if bpp not in (1, 2):
            raise ValueError(f"Invalid bpp : {bpp}")
        elif bpp == 2:
            split_line = split_double_byte_line
        else:
            split_line = lambda l: list(l)

        for i in range(0, len(self.chart_lines), 4):
            yield [split_line(self.chart_lines[i + j]) for j in range(4)]


class MonoColumnParser(JubeatAnalyserParser):
    def __init__(self):
        super().__init__()
        self.sections: List[MonoColumnLoadedSection] = []

    def do_memo(self):
        raise ValueError(
            "This file indicates it's using another jubeat analyser format "
            "than the one the currently selected parser is designed for"
        )

    do_boogie = do_memo2 = do_memo1 = do_memo

    def do_bpp(self, value):
        if self.sections:
            raise ValueError(
                "This file apparently changes its bytes per panel value (#bpp) "
                "halfway through the chart, jubeatools does not handle that"
            )
        else:
            self._do_bpp(value)

    def move_to_next_section(self):
        if len(self.current_chart_lines) % 4 != 0:
            raise SyntaxError("Current section is missing chart lines")
        else:
            self.sections.append(
                MonoColumnLoadedSection(
                    chart_lines=self.current_chart_lines,
                    symbols=deepcopy(self.symbols),
                    length=self.beats_per_section,
                    tempo=self.current_tempo,
                )
            )
            self.current_chart_lines = []
            self.section_starting_beat += self.beats_per_section

    def append_chart_line(self, line: str):
        if self.bytes_per_panel == 1 and len(line) != 4:
            raise SyntaxError(f"Invalid chart line for #bpp=1 : {line}")
        elif self.bytes_per_panel == 2 and len(line.encode("shift-jis-2004")) != 8:
            raise SyntaxError(f"Invalid chart line for #bpp=2 : {line}")
        self.current_chart_lines.append(line)

    def load_line(self, raw_line: str):
        line = raw_line.strip()
        if is_command(line):
            command, value = parse_command(line)
            self.handle_command(command, value)
        elif is_symbol_definition(line):
            symbol, timing = parse_symbol_definition(line)
            self.define_symbol(symbol, timing)
        elif is_mono_column_chart_line(line):
            chart_line = parse_mono_column_chart_line(line)
            self.append_chart_line(chart_line)
        elif is_separator(line):
            self.move_to_next_section()
        elif not (is_empty_line(line) or self.is_short_line(line)):
            raise SyntaxError(f"not a valid mono-column file line : {line}")

    def notes(self) -> Iterator[Union[TapNote, LongNote]]:
        if self.hold_by_arrow:
            yield from self._iter_notes()
        else:
            yield from self._iter_notes_without_longs()

    def _iter_blocs(
        self,
    ) -> Iterator[Tuple[Decimal, MonoColumnLoadedSection, List[List[str]]]]:
        section_starting_beat = Decimal(0)
        for section in self.sections:
            for bloc in section.blocs():
                yield section_starting_beat, section, bloc
            section_starting_beat += section.length

    def _iter_notes(self) -> Iterator[Union[TapNote, LongNote]]:
        unfinished_longs: Dict[NotePosition, UnfinishedLongNote] = {}
        for section_starting_beat, section, bloc in self._iter_blocs():
            should_skip: Set[NotePosition] = set()

            # 1/3 : look for ends to unfinished long notes
            for pos, unfinished_long in unfinished_longs.items():
                x, y = astuple(pos)
                symbol = bloc[y][x]
                if self.circle_free:
                    if symbol in CIRCLE_FREE_SYMBOLS:
                        should_skip.add(pos)
                        symbol_time = CIRCLE_FREE_TO_DECIMAL_TIME[symbol]
                        note_time = decimal_to_beats(
                            section_starting_beat + symbol_time
                        )
                        yield unfinished_long.ends_at(note_time)
                    elif symbol in section.symbols:
                        raise SyntaxError(
                            "Can't have a note symbol on the holding square of"
                            " an unfinished long note when #circlefree is on"
                        )
                else:
                    if symbol in section.symbols:
                        should_skip.add(pos)
                        symbol_time = section.symbols[symbol]
                        note_time = decimal_to_beats(
                            section_starting_beat + symbol_time
                        )
                        yield unfinished_long.ends_at(note_time)

            unfinished_longs = {
                k: unfinished_longs[k] for k in unfinished_longs.keys() - should_skip
            }

            # 2/3 : look for new long notes starting on this bloc
            arrow_to_note_candidates = find_long_note_candidates(
                bloc, section.symbols.keys(), should_skip
            )
            if arrow_to_note_candidates:
                solution = pick_correct_long_note_candidates(
                    arrow_to_note_candidates, bloc,
                )
                for arrow_pos, note_pos in solution.items():
                    should_skip.add(arrow_pos)
                    should_skip.add(note_pos)
                    symbol = bloc[note_pos.y][note_pos.x]
                    symbol_time = section.symbols[symbol]
                    note_time = decimal_to_beats(section_starting_beat + symbol_time)
                    unfinished_longs[note_pos] = UnfinishedLongNote(
                        time=note_time, position=note_pos, tail_tip=arrow_pos
                    )

            # 3/3 : find regular notes
            for y, x in product(range(4), range(4)):
                position = NotePosition(x, y)
                if position in should_skip:
                    continue
                symbol = bloc[y][x]
                if symbol in section.symbols:
                    symbol_time = section.symbols[symbol]
                    note_time = decimal_to_beats(section_starting_beat + symbol_time)
                    yield TapNote(note_time, position)

    def _iter_notes_without_longs(self) -> Iterator[TapNote]:
        section_starting_beat = Decimal(0)
        for section in self.sections:
            for bloc, y, x in product(section.blocs(), range(4), range(4)):
                symbol = bloc[y][x]
                if symbol in section.symbols:
                    symbol_time = section.symbols[symbol]
                    note_time = decimal_to_beats(section_starting_beat + symbol_time)
                    position = NotePosition(x, y)
                    yield TapNote(note_time, position)
            section_starting_beat += section.length


def load_mono_column(path: Path) -> Song:
    files = load_files(path)
    charts = [_load_mono_column_file(lines) for _, lines in files.items()]
    return reduce(lambda a, b: a.merge(b), charts)


def _load_mono_column_file(lines: List[str]) -> Song:
    parser = MonoColumnParser()
    for i, raw_line in enumerate(lines):
        try:
            parser.load_line(raw_line)
        except Exception as e:
            raise SyntaxError(
                f"Error while parsing mono column line {i} :\n"
                f"{type(e).__name__}: {e}"
            ) from None

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
