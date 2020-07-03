import re
import warnings
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
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
from ..symbol import is_symbol_definition, parse_symbol_definition
from .commons import CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS

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
    symbol: Decimal("0.25") * index for index, symbol in enumerate(NOTE_SYMBOLS)
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

    def blocs(self, bpp=2) -> Iterator[List[List[str]]]:
        if bpp not in (1, 2):
            raise ValueError(f"Invalid bpp : {bpp}")
        elif bpp == 2:
            split_line = split_chart_line
        else:
            split_line = lambda l: list(l)

        for i in range(0, len(self.chart_lines), 4):
            yield [split_line(self.chart_lines[i + j]) for j in range(4)]


@dataclass(frozen=True)
class UnfinishedLongNote:
    time: BeatsTime
    position: NotePosition
    tail_tip: NotePosition

    def ends_at(self, end: BeatsTime) -> LongNote:
        if end < self.time:
            raise ValueError(
                f"Invalid end time ({end}) for long note starting at {self.time}"
            )
        return LongNote(
            time=self.time,
            position=self.position,
            duration=end - self.time,
            tail_tip=self.tail_tip,
        )


LONG_ARROW_RIGHT = {
    ">",  # U+003E : GREATER-THAN SIGN
    "＞",  # U+FF1E : FULLWIDTH GREATER-THAN SIGN
}

LONG_ARROW_LEFT = {
    "<",  # U+003C : LESS-THAN SIGN
    "＜",  # U+FF1C : FULLWIDTH LESS-THAN SIGN
}

LONG_ARROW_DOWN = {
    "V",  # U+0056 : LATIN CAPITAL LETTER V
    "v",  # U+0076 : LATIN SMALL LETTER V
    "Ⅴ",  # U+2164 : ROMAN NUMERAL FIVE
    "ⅴ",  # U+2174 : SMALL ROMAN NUMERAL FIVE
    "∨",  # U+2228 : LOGICAL OR
    "Ｖ",  # U+FF36 : FULLWIDTH LATIN CAPITAL LETTER V
    "ｖ",  # U+FF56 : FULLWIDTH LATIN SMALL LETTER V
}

LONG_ARROW_UP = {
    "^",  # U+005E : CIRCUMFLEX ACCENT
    "∧",  # U+2227 : LOGICAL AND
}

LONG_ARROWS = LONG_ARROW_LEFT | LONG_ARROW_DOWN | LONG_ARROW_UP | LONG_ARROW_RIGHT

LONG_DIRECTION = {
    **{c: (1, 0) for c in LONG_ARROW_RIGHT},
    **{c: (-1, 0) for c in LONG_ARROW_LEFT},
    **{c: (0, 1) for c in LONG_ARROW_DOWN},
    **{c: (0, -1) for c in LONG_ARROW_UP},
}

CIRCLE_FREE_TO_DECIMAL_TIME = {
    c: Decimal("0.25") * i for i, c in enumerate(CIRCLE_FREE_SYMBOLS)
}


def _distance(a: NotePosition, b: NotePosition) -> float:
    return abs(complex(*a.as_tuple()) - complex(*b.as_tuple()))


def _long_note_solution_heuristic(
    solution: Dict[NotePosition, NotePosition]
) -> Tuple[int, int, int]:
    c = Counter(int(_distance(k, v)) for k, v in solution.items())
    return (c[3], c[2], c[1])


def _is_simple_solution(solution, domains) -> bool:
    return all(
        solution[v] == min(domains[v], key=lambda e: _distance(e, v))
        for v in solution.keys()
    )


def decimal_to_beats(current_beat: Decimal, symbol_timing: Decimal) -> BeatsTime:
    decimal_time = current_beat + symbol_timing
    return BeatsTime(decimal_time).limit_denominator(240)


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
        self.hold_by_arrow = False
        self.circle_free = False
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
        bpp = int(value)
        if self.sections:
            raise ValueError(
                "jubeatools does not handle changing the bytes per panel value halfway"
            )
        elif bpp not in (1, 2):
            raise ValueError(f"Unexcpected bpp value : {value}")
        elif self.circle_free and bpp == 1:
            raise ValueError("#bpp can only be 2 when #circlefree is activated")
        else:
            self.bytes_per_panel = int(value)

    def do_holdbyarrow(self, value):
        self.hold_by_arrow = int(value) == 1

    def do_holdbytilde(self, value):
        if int(value):
            raise ValueError("jubeatools does not support #holdbytilde")

    def do_circlefree(self, raw_value):
        activate = bool(int(raw_value))
        if activate and self.bytes_per_panel != 2:
            raise ValueError("#circlefree can only be activated when #bpp=2")
        self.circle_free = activate

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

    def notes(self) -> Iterator[Union[TapNote, LongNote]]:
        if self.hold_by_arrow:
            yield from self._iter_notes()
        else:
            yield from self._iter_notes_without_longs()

    def _iter_blocs(
        self,
    ) -> Iterator[Tuple[Decimal, MonoColumnLoadedSection, List[List[str]]]]:
        current_beat = Decimal(0)
        for section in self.sections:
            for bloc in section.blocs():
                yield current_beat, section, bloc
            current_beat += section.length

    def _iter_notes(self) -> Iterator[Union[TapNote, LongNote]]:
        unfinished_longs: Dict[NotePosition, UnfinishedLongNote] = {}
        for current_beat, section, bloc in self._iter_blocs():
            should_skip: Set[NotePosition] = set()

            # 1/3 : look for ends to unfinished long notes
            for pos, unfinished_long in unfinished_longs.items():
                x, y = pos.as_tuple()
                symbol = bloc[y][x]
                if self.circle_free:
                    if symbol in CIRCLE_FREE_SYMBOLS:
                        should_skip.add(pos)
                        symbol_time = CIRCLE_FREE_TO_DECIMAL_TIME[symbol]
                        note_time = decimal_to_beats(current_beat, symbol_time)
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
                        note_time = decimal_to_beats(current_beat, symbol_time)
                        yield unfinished_long.ends_at(note_time)

            unfinished_longs = {
                k: unfinished_longs[k] for k in unfinished_longs.keys() - should_skip
            }

            # 2/3 : look for new long notes starting on this bloc
            arrow_to_note_candidates: Dict[NotePosition, Set[NotePosition]] = {}
            for y, x in product(range(4), range(4)):
                pos = NotePosition(x, y)
                if pos in should_skip:
                    continue
                symbol = bloc[y][x]
                if symbol not in LONG_ARROWS:
                    continue
                # at this point we are sure we have a long arrow
                # we need to check in its direction for note candidates
                note_candidates: Set[Tuple[int, int]] = set()
                𝛿pos = LONG_DIRECTION[symbol]
                candidate = NotePosition(x, y) + 𝛿pos
                while 0 <= candidate.x < 4 and 0 <= candidate.y < 4:
                    if candidate in should_skip:
                        continue
                    new_symbol = bloc[candidate.y][candidate.x]
                    if new_symbol in section.symbols:
                        note_candidates.add(candidate)
                    candidate += 𝛿pos
                # if no notes have been crossed, we just ignore the arrow
                if note_candidates:
                    arrow_to_note_candidates[pos] = note_candidates

            # Believe it or not, assigning each arrow to a valid note candidate
            # involves whipping out a CSP solver
            if arrow_to_note_candidates:
                problem = constraint.Problem()
                for arrow_pos, note_candidates in arrow_to_note_candidates.items():
                    problem.addVariable(arrow_pos, list(note_candidates))
                problem.addConstraint(constraint.AllDifferentConstraint())
                solutions = problem.getSolutions()
                if not solutions:
                    raise SyntaxError(
                        "Invalid long note arrow pattern in bloc :\n"
                        + "\n".join("".join(line) for line in bloc)
                    )
                solution = min(solutions, key=_long_note_solution_heuristic)
                if len(solutions) > 1 and not _is_simple_solution(
                    solution, arrow_to_note_candidates
                ):
                    warnings.warn(
                        "Ambiguous arrow pattern in bloc :\n"
                        + "\n".join("".join(line) for line in bloc)
                        + "\n"
                        "The resulting long notes might not be what you expect"
                    )
                for arrow_pos, note_pos in solution.items():
                    should_skip.add(arrow_pos)
                    should_skip.add(note_pos)
                    symbol = bloc[note_pos.y][note_pos.x]
                    symbol_time = section.symbols[symbol]
                    note_time = decimal_to_beats(current_beat, symbol_time)
                    unfinished_longs[note_pos] = UnfinishedLongNote(
                        time=note_time, position=note_pos, tail_tip=arrow_pos,
                    )

            # 3/3 : find regular notes
            for y, x in product(range(4), range(4)):
                position = NotePosition(x, y)
                if position in should_skip:
                    continue
                symbol = bloc[y][x]
                if symbol in section.symbols:
                    symbol_time = section.symbols[symbol]
                    note_time = decimal_to_beats(current_beat, symbol_time)
                    yield TapNote(note_time, position)

    def _iter_notes_without_longs(self) -> Iterator[TapNote]:
        current_beat = Decimal(0)
        for section in self.sections:
            for bloc, y, x in product(section.blocs(), range(4), range(4)):
                symbol = bloc[y][x]
                if symbol in section.symbols:
                    symbol_time = section.symbols[symbol]
                    note_time = decimal_to_beats(current_beat, symbol_time)
                    position = NotePosition(x, y)
                    yield TapNote(note_time, position)
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
            level=state.level,
            timing=timing,
            notes=sorted(state.notes(), key=lambda n: (n.time, n.position)),
        )
    }
    return Song(metadata=metadata, charts=charts)
