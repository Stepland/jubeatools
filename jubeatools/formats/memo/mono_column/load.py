import heapq
import re
from collections import ChainMap, defaultdict, namedtuple
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from io import StringIO
from itertools import chain, product
from typing import IO, Dict, Iterable, Iterator, List, Optional, Tuple, Union

from more_itertools import collapse, intersperse, windowed
from parsimonious import Grammar, NodeVisitor, ParseError
from path import Path
from sortedcontainers import SortedKeyList, SortedSet

from jubeatools import __version__
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
)

from ..command import is_command, parse_command
from ..symbol import is_symbol_definition, parse_symbol_definition

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


EMPTY_LINE = re.compile(r"\s*(//.*)?")


def is_empty_line(line: str) -> bool:
    return bool(EMPTY_LINE.match(line))


DIFFICULTIES = {1: "BSC", 2: "ADV", 3: "EXT"}

SYMBOL_TO_DECIMAL_TIME = {
    symbol: Decimal("0.25") * index for index, symbol in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯")
}


def split_chart_line(line: str) -> List[str]:
    """Split a #bpp=2 chart line into symbols :
    Given the symbol definition : *25:6
    >>> split_chart_line("25口口25")
    ... ["25","口","口","25"]
    >>> split_chart_line("口⑪①25")
    ... ["口","⑪","①","25"]
    """
    encoded_line = line.encode("shift_jis_2004")
    if len(encoded_line) % 2 != 0:
        raise ValueError(f"Invalid chart line : {line}")
    symbols = []
    for i in range(0, len(encoded_line), 2):
        symbols.append(encoded_line[i : i + 2].decode("shift_jis_2004"))
    return symbols


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

    def blocs(self, bpp=2) -> Iterable[List[List[str]]]:
        if bpp not in (1, 2):
            raise ValueError(f"Invalid bpp : {bpp}")
        elif bpp == 2:
            split_line = split_chart_line
        else:
            split_line = lambda l: list(l)

        for i in range(0, len(self.chart_lines), 4):
            yield [split_line(self.chart_lines[i + j]) for j in range(4)]


class MonoColumnParser:
    def __init__(self):
        self.music = None
        self.symbols = deepcopy(SYMBOL_TO_DECIMAL_TIME)
        self.current_beat = Decimal("0")
        self.current_tempo = None
        self.current_chart_lines = []
        self.timing_events = []
        self.offset = 0
        self.beats_per_section = 4
        self.bytes_per_panel = 2
        self.level = 1
        self.difficulty = None
        self.title = None
        self.artist = None
        self.jacket = None
        self.preview_start = None
        self.sections: List[MonoColumnLoadedSection] = []

    def handle_command(self, command, value=None):
        try:
            method = getattr(self, f"do_{command}")
        except AttributeError:
            raise SyntaxError(f"Unknown analyser command : {command}") from None

        if value is not None:
            method(value)
        else:
            method()

    def do_m(self, value):
        self.music = value

    def do_t(self, value):
        self.current_tempo = Decimal(value)
        self.timing_events.append(BPMEvent(self.current_beat, BPM=self.current_tempo))

    def do_o(self, value):
        self.offset = int(value)

    def do_b(self, value):
        self.beats_per_section = Decimal(value)

    def do_memo(self):
        raise ValueError("This is not a mono-column file")

    do_boogie = do_memo2 = do_memo1 = do_memo

    def do_pw(self, value):
        if int(value) != 4:
            raise ValueError("jubeatools only supports 4×4 charts")

    do_ph = do_pw

    def do_lev(self, value):
        self.level = int(value)

    def do_dif(self, value):
        dif = int(value)
        if dif <= 0:
            raise ValueError(f"Unknown chart difficulty : {dif}")
        if dif < 4:
            self.difficulty = DIFFICULTIES[dif]
        else:
            self.difficulty = f"EDIT-{dif-3}"

    def do_title(self, value):
        self.title = value

    def do_artist(self, value):
        self.artist = value

    def do_jacket(self, value):
        self.jacket = value

    def do_prevpos(self, value):
        self.preview_start = int(value)

    def do_bpp(self, value):
        if self.sections:
            raise ValueError(
                "jubeatools does not handle changing the bytes per panel value halfway"
            )
        elif int(value) not in (1, 2):
            raise ValueError(f"Unexcpected bpp value : {value}")
        else:
            self.bytes_per_panel = int(value)

    def define_symbol(self, symbol: str, timing: Decimal):
        bpp = self.bytes_per_panel
        length_as_shift_jis = len(symbol.encode("shift_jis_2004"))
        if length_as_shift_jis != bpp:
            raise ValueError(
                f"Invalid symbol definition. Since #bpp={bpp}, timing symbols "
                f"should be {bpp} bytes long but '{symbol}' is {length_as_shift_jis}"
            )
        if timing > self.beats_per_section:
            message = (
                "Invalid symbol definition conscidering the number of beats per section :\n"
                f"*{symbol}:{timing}"
            )
            raise ValueError(message)
        self.symbols[symbol] = timing

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
            self.current_beat += self.beats_per_section

    def append_chart_line(self, line: str):
        if self.bytes_per_panel == 1 and len(line) != 4:
            raise SyntaxError(f"Invalid chart line for #bpp=1 : {line}")
        elif self.bytes_per_panel == 2 and len(line.encode("shift_jis_2004")) != 8:
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
        elif not is_empty_line(line):
            raise SyntaxError(f"not a valid #memo line : {line}")

    def notes(self) -> Iterable[Union[TapNote, LongNote]]:
        current_beat = Decimal(0)
        for section in self.sections:
            for bloc, y, x in product(section.blocs(), range(4), range(4)):
                symbol = bloc[y][x]
                if symbol in section.symbols:
                    decimal_time = current_beat + section.symbols[symbol]
                    fraction_time = BeatsTime(decimal_time).limit_denominator(240)
                    position = NotePosition(x, y)
                    yield TapNote(fraction_time, position)
            current_beat += section.length


def load_mono_column(path: Path) -> Song:
    # The vast majority of memo files you will encounter will be propely
    # decoded using shift_jis_2004. Get ready for endless fun with the small
    # portion of files that won't
    with open(path, encoding="shift_jis_2004") as f:
        lines = f.readlines()

    state = MonoColumnParser()
    for i, raw_line in enumerate(lines):
        try:
            state.load_line(raw_line)
        except Exception as e:
            raise SyntaxError(
                f"Error while parsing mono column line {i} :\n"
                f"{type(e).__name__}: {e}"
            ) from None

    metadata = Metadata(
        title=state.title, artist=state.artist, audio=state.music, cover=state.jacket
    )
    if state.preview_start is not None:
        metadata.preview_start = SecondsTime(state.preview_start) / 1000
        metadata.preview_length = SecondsTime(10)

    timing = Timing(
        events=state.timing_events, beat_zero_offset=SecondsTime(state.offset) / 1000
    )
    charts = {
        state.difficulty: Chart(
            level=state.level, timing=timing, notes=list(state.notes())
        )
    }
    return Song(metadata=metadata, charts=charts)
