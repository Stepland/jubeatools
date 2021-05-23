"""Collection of parsing tools that are common to all the jubeat analyser formats"""

import re
import warnings
from collections import Counter
from copy import deepcopy
from dataclasses import astuple, dataclass
from decimal import Decimal
from itertools import product, zip_longest
from pathlib import Path
from typing import AbstractSet, Dict, List, Optional, Set, Tuple, Union

import constraint
from parsimonious import Grammar, NodeVisitor, ParseError
from parsimonious.nodes import Node

from jubeatools.formats.load_tools import make_folder_loader, round_beats
from jubeatools.song import BeatsTime, BPMEvent, Difficulty, LongNote, NotePosition

from .symbols import (
    CIRCLE_FREE_SYMBOLS,
    LONG_ARROW_DOWN,
    LONG_ARROW_LEFT,
    LONG_ARROW_RIGHT,
    LONG_ARROW_UP,
    NOTE_SYMBOLS,
)

DIFFICULTIES = {
    1: Difficulty.BASIC,
    2: Difficulty.ADVANCED,
    3: Difficulty.EXTREME,
}

SYMBOL_TO_BEATS_TIME = {c: BeatsTime("1/4") * i for i, c in enumerate(NOTE_SYMBOLS)}

CIRCLE_FREE_TO_BEATS_TIME = {
    c: BeatsTime("1/4") * i for i, c in enumerate(CIRCLE_FREE_SYMBOLS)
}

CIRCLE_FREE_TO_NOTE_SYMBOL = dict(zip(CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS))

LONG_ARROWS = LONG_ARROW_LEFT | LONG_ARROW_DOWN | LONG_ARROW_UP | LONG_ARROW_RIGHT

LONG_DIRECTION = {
    **{c: (1, 0) for c in LONG_ARROW_RIGHT},
    **{c: (-1, 0) for c in LONG_ARROW_LEFT},
    **{c: (0, 1) for c in LONG_ARROW_DOWN},
    **{c: (0, -1) for c in LONG_ARROW_UP},
}


EMPTY_LINE = re.compile(r"\s*(//.*)?")


# Any unicode character that's both :
#  - confusable with a dash/hyphen
#  - encodable in shift-jis-2004
# Gets added to the list of characters to be ignored in the timing section
EMPTY_BEAT_SYMBOLS = {
    "一",  # U+4E00 - CJK UNIFIED IDEOGRAPH-4E00
    "－",  # U+FF0D - FULLWIDTH HYPHEN-MINUS
    "ー",  # U+30FC - KATAKANA-HIRAGANA PROLONGED SOUND MARK
    "─",  # U+2500 - BOX DRAWINGS LIGHT HORIZONTAL
    "―",  # U+2015 - HORIZONTAL BAR
    "━",  # U+2501 - BOX DRAWINGS HEAVY HORIZONTAL
    "–",  # U+2013 - EN DASH
    "‐",  # U+2010 - HYPHEN
    "-",  # U+002D - HYPHEN-MINUS
    "−",  # U+2212 - MINUS SIGN
}


SEPARATOR = re.compile(r"--.*")


def is_separator(line: str) -> bool:
    return bool(SEPARATOR.match(line))


double_column_chart_line_grammar = Grammar(
    r"""
    line            = ws position_part ws (timing_part ws)? comment?
    position_part   = ~r"[^*#:|/\s]{4,8}"
    timing_part     = "|" ~r"[^*#:|/\s]*" "|"
    ws              = ~r"[\t \u3000]*"
    comment         = ~r"//.*"
"""
)


@dataclass
class DoubleColumnChartLine:
    position: str
    timing: Optional[str]

    def __str__(self) -> str:
        return f"{self.position} |{self.timing}|"

    def raise_if_unfit(self, bytes_per_panel: int) -> None:
        self.raise_if_position_unfit(bytes_per_panel)
        self.raise_if_timing_unfit(bytes_per_panel)

    def raise_if_position_unfit(self, bytes_per_panel: int) -> None:
        expected_length = 4 * bytes_per_panel
        actual_length = len(
            self.position.encode("shift-jis-2004", errors="surrogateescape")
        )
        if expected_length != actual_length:
            raise SyntaxError(
                f"Invalid position part. Since #bpp={bytes_per_panel}, the "
                f"position part of a line should be {expected_length} bytes long, "
                f"but {self.position!r} is {actual_length} bytes long"
            )

    def raise_if_timing_unfit(self, bytes_per_panel: int) -> None:
        if self.timing is None:
            return

        length = len(self.timing.encode("shift-jis-2004", errors="surrogateescape"))
        if length % bytes_per_panel != 0:
            raise SyntaxError(
                f"Invalid timing part. Since #bpp={bytes_per_panel}, the timing "
                f"part of a line should be divisible by {bytes_per_panel}, but "
                f"{self.timing!r} is {length} bytes long so it's not"
            )


class DoubleColumnChartLineVisitor(NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.pos_part: Optional[str] = None
        self.time_part: Optional[str] = None

    def visit_line(
        self, node: Node, visited_children: List[Node]
    ) -> DoubleColumnChartLine:
        if self.pos_part is None:
            raise ValueError("No positional part found after parsing line")
        return DoubleColumnChartLine(self.pos_part, self.time_part)

    def visit_position_part(self, node: Node, visited_children: List[Node]) -> None:
        self.pos_part = node.text

    def visit_timing_part(self, node: Node, visited_children: List[Node]) -> None:
        _, time_part, _ = node.children
        self.time_part = time_part.text

    def generic_visit(self, node: Node, visited_children: List[Node]) -> None:
        ...


def is_double_column_chart_line(line: str) -> bool:
    try:
        double_column_chart_line_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_double_column_chart_line(line: str) -> DoubleColumnChartLine:
    return DoubleColumnChartLineVisitor().visit(double_column_chart_line_grammar.parse(line))  # type: ignore


def is_empty_line(line: str) -> bool:
    return bool(EMPTY_LINE.fullmatch(line))


def split_double_byte_line(line: str) -> List[str]:
    """Split a #bpp=2 chart line into symbols.
    For example, Assuming "25" was defined as a symbol earlier :
    >>> split_chart_line("25口口25")
    ... ["25","口","口","25"]
    >>> split_chart_line("口⑪①25")
    ... ["口","⑪","①","25"]
    """
    encoded_line = line.encode("shift-jis-2004", errors="surrogateescape")
    if len(encoded_line) % 2 != 0:
        raise ValueError(
            "Line of odd length encountered while trying to split a double-byte "
            f"line : {line!r}"
        )
    symbols = []
    for i in range(0, len(encoded_line), 2):
        symbols.append(
            encoded_line[i : i + 2].decode("shift-jis-2004", errors="surrogateescape")
        )
    return symbols


@dataclass(frozen=True)
class UnfinishedLongNote:
    time: BeatsTime
    position: NotePosition
    tail_tip: NotePosition

    def ends_at(self, end: BeatsTime) -> LongNote:
        if end < self.time:
            raise ValueError(
                "Invalid end time. A long note starting at "
                f"{self.time} cannot end at {end} (which is earlier)"
            )
        return LongNote(
            time=self.time,
            position=self.position,
            duration=end - self.time,
            tail_tip=self.tail_tip,
        )


def find_long_note_candidates(
    bloc: List[List[str]],
    note_symbols: AbstractSet[str],
    should_skip: AbstractSet[NotePosition],
) -> Dict[NotePosition, Set[NotePosition]]:
    "Return a dict of arrow position to landing note candidates"
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
        note_candidates = set()
        𝛿pos = LONG_DIRECTION[symbol]
        candidate = NotePosition(x, y) + 𝛿pos
        while True:
            try:
                candidate = NotePosition.from_raw_position(candidate)
            except ValueError:
                break

            if candidate not in should_skip:
                new_symbol = bloc[candidate.y][candidate.x]
                if new_symbol in note_symbols:
                    note_candidates.add(candidate)
            candidate += 𝛿pos

        # if no notes have been crossed, we just ignore the arrow
        if note_candidates:
            arrow_to_note_candidates[pos] = note_candidates

    return arrow_to_note_candidates


Solution = Dict[NotePosition, NotePosition]
Candidates = Dict[NotePosition, Set[NotePosition]]


def pick_correct_long_note_candidates(
    arrow_to_note_candidates: Candidates,
    bloc: List[List[str]],
) -> Solution:
    """Believe it or not, assigning each arrow to a valid note candidate
    involves whipping out a CSP solver.
    Returns an arrow_pos -> note_pos mapping
    """
    problem = constraint.Problem()
    for arrow_pos, note_candidates in arrow_to_note_candidates.items():
        problem.addVariable(arrow_pos, list(note_candidates))
    problem.addConstraint(constraint.AllDifferentConstraint())
    solutions: List[Solution] = problem.getSolutions()
    if not solutions:
        raise SyntaxError(
            "Impossible arrow pattern found in block :\n"
            + "\n".join("".join(line) for line in bloc)
        )
    solution = min(solutions, key=long_note_solution_heuristic)
    if len(solutions) > 1 and not is_simple_solution(
        solution, arrow_to_note_candidates
    ):
        warnings.warn(
            "Ambiguous arrow pattern in bloc :\n"
            + "\n".join("".join(line) for line in bloc)
            + "\n"
            "The resulting long notes might not be what you expect"
        )
    return solution


def note_distance(a: NotePosition, b: NotePosition) -> float:
    return abs(complex(*astuple(a)) - complex(*astuple(b)))


def long_note_solution_heuristic(solution: Solution) -> Tuple[int, int, int]:
    c = Counter(int(note_distance(k, v)) for k, v in solution.items())
    return (c[3], c[2], c[1])


def is_simple_solution(solution: Solution, domains: Candidates) -> bool:
    return all(
        solution[v] == min(domains[v], key=lambda e: note_distance(e, v))
        for v in solution.keys()
    )


class JubeatAnalyserParser:
    def __init__(self) -> None:
        self.music: Optional[str] = None
        self.symbols = deepcopy(SYMBOL_TO_BEATS_TIME)
        self.section_starting_beat = BeatsTime(0)
        self.current_tempo = Decimal(120)
        self.timing_events: List[BPMEvent] = []
        self.offset = 0
        self.beats_per_section = BeatsTime(4)
        self.bytes_per_panel = 2
        self.level = Decimal(1)
        self.difficulty: Optional[str] = None
        self.title: Optional[str] = None
        self.artist: Optional[str] = None
        self.jacket: Optional[str] = None
        self.preview_start: Optional[int] = None
        self.hold_by_arrow = False
        self.circle_free = False

    def handle_command(self, command: str, value: Optional[str] = None) -> None:
        try:
            method = getattr(self, f"do_{command}")
        except AttributeError:
            raise SyntaxError(f"Unknown jubeat analyser command : {command}") from None

        if value is not None:
            method(value)
        else:
            method()

    def do_b(self, value: str) -> None:
        self.beats_per_section = round_beats(Decimal(value))

    def do_m(self, value: str) -> None:
        self.music = value

    def do_o(self, value: str) -> None:
        self.offset = int(value)

    def do_r(self, value: str) -> None:
        self.offset += int(value)

    def do_t(self, value: str) -> None:
        self.current_tempo = Decimal(value)
        self.timing_events.append(
            BPMEvent(
                time=self._current_beat(),
                BPM=self.current_tempo,
            )
        )

    def do_pw(self, value: str) -> None:
        if int(value) != 4:
            raise ValueError("jubeatools only supports 4×4 charts")

    do_ph = do_pw

    def do_lev(self, value: str) -> None:
        self.level = Decimal(value)

    def do_dif(self, value: str) -> None:
        dif = int(value)
        if dif < 4:
            self.difficulty = DIFFICULTIES[dif]
        else:
            self.difficulty = f"EDIT"

    def do_title(self, value: str) -> None:
        self.title = value

    def do_artist(self, value: str) -> None:
        self.artist = value

    def do_jacket(self, value: str) -> None:
        self.jacket = value

    def do_prevpos(self, value: str) -> None:
        self.preview_start = int(value)

    def _do_bpp(self, value: Union[int, str]) -> None:
        bpp = int(value)
        if bpp not in (1, 2):
            raise ValueError(f"Unexcpected bpp value : {value}")
        elif self.circle_free and bpp == 1:
            raise ValueError("Can't set #bpp to 1 when #circlefree is on")
        else:
            self.bytes_per_panel = int(value)

    def do_holdbyarrow(self, value: str) -> None:
        self.hold_by_arrow = int(value) == 1

    def do_holdbytilde(self, value: str) -> None:
        raise NotImplementedError("jubeatools does not support #holdbytilde")

    def do_circlefree(self, raw_value: str) -> None:
        activate = bool(int(raw_value))
        if activate and self.bytes_per_panel != 2:
            raise ValueError("#circlefree can only be on when #bpp=2")
        self.circle_free = activate

    def _wrong_format(self, f: str) -> None:
        raise ValueError(
            f"{f} command means that this file uses another jubeat analyser "
            "format than the one the currently selected parser is designed for"
        )

    def do_memo(self) -> None:
        self._wrong_format("#memo")

    def do_memo1(self) -> None:
        self._wrong_format("#memo1")

    def do_boogie(self) -> None:
        self._wrong_format("#boogie")

    def do_memo2(self) -> None:
        self._wrong_format("#memo2")

    def define_symbol(self, symbol: str, timing: Decimal) -> None:
        bpp = self.bytes_per_panel
        length_as_shift_jis = len(
            symbol.encode("shift-jis-2004", errors="surrogateescape")
        )
        if length_as_shift_jis != bpp:
            raise ValueError(
                f"Invalid symbol definition. Since #bpp={bpp}, timing symbols "
                f"should be {bpp} bytes long but '{symbol}' is {length_as_shift_jis}"
            )
        if timing > self.beats_per_section:
            raise ValueError(
                f"Invalid symbol definition. Since sections only last "
                f"{self.beats_per_section} beats, a symbol cannot happen "
                f"afterwards at {timing}"
            )
        self.symbols[symbol] = round_beats(timing)

    def is_short_line(self, line: str) -> bool:
        return (
            len(line.encode("shift-jis-2004", errors="surrogateescape"))
            < self.bytes_per_panel * 4
        )

    def _split_chart_line(self, line: str) -> List[str]:
        if self.bytes_per_panel == 2:
            return split_double_byte_line(line)
        else:
            return list(line)

    def raise_if_separator(self, line: str, format_: str) -> None:
        if is_separator(line):
            raise SyntaxError(
                'Found a separator line (starting with "--") but the file '
                f"indicates it's using {format_} format, if the file is actually "
                f"in mono-column format (1列形式) there should be no {format_} line"
            )

    def _current_beat(self) -> BeatsTime:
        raise NotImplementedError


@dataclass
class DoubleColumnFrame:
    position_part: List[List[str]]
    timing_part: List[List[str]]

    def __str__(self) -> str:
        res = []
        for pos, time in zip_longest(self.position_part, self.timing_part):
            line = [f"{''.join(pos)}"]
            if time is not None:
                line += [f"|{''.join(time)}|"]
            res += [" ".join(line)]
        return "\n".join(res)


def read_jubeat_analyser_file(path: Path) -> Optional[List[str]]:
    """The vast majority of memo files you will encounter will be propely
    decoded using shift-jis-2004. Some won't but jubeat analyser works at the
    byte level so it doesn't care, here we use surrogateescape to handle
    potential decoding errors"""
    return path.read_text(encoding="shift-jis-2004", errors="surrogateescape").split(
        "\n"
    )


load_folder = make_folder_loader(
    glob_pattern="*.txt",
    file_loader=read_jubeat_analyser_file,
)
