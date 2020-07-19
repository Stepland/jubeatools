"""Collection of parsing tools that are common to all the jubeat analyser formats"""
import re
import warnings
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from itertools import product, zip_longest
from typing import Dict, Iterator, List, Optional, Set, Tuple

import constraint
from parsimonious import Grammar, NodeVisitor, ParseError

from jubeatools.song import BeatsTime, BPMEvent, LongNote, NotePosition

from .symbols import (
    CIRCLE_FREE_SYMBOLS,
    LONG_ARROW_DOWN,
    LONG_ARROW_LEFT,
    LONG_ARROW_RIGHT,
    LONG_ARROW_UP,
    NOTE_SYMBOLS,
)

DIFFICULTIES = {1: "BSC", 2: "ADV", 3: "EXT"}

SYMBOL_TO_DECIMAL_TIME = {c: Decimal("0.25") * i for i, c in enumerate(NOTE_SYMBOLS)}

CIRCLE_FREE_TO_DECIMAL_TIME = {
    c: Decimal("0.25") * i for i, c in enumerate(CIRCLE_FREE_SYMBOLS)
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
#  - encodable in shift_jis_2004
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


double_column_chart_line_grammar = Grammar(
    r"""
    line            = ws position_part ws (timing_part ws)? comment?
    position_part   = ~r"[^*#:|/\s]{4,8}"
    timing_part     = "|" ~r"[^*#:|/\s]*" "|"
    ws              = ~r"[\t ]*"
    comment         = ~r"//.*"
"""
)


@dataclass
class DoubleColumnChartLine:
    position: str
    timing: Optional[str]

    def __str__(self):
        return f"{self.position} |{self.timing}|"


class DoubleColumnChartLineVisitor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.pos_part = None
        self.time_part = None

    def visit_line(self, node, visited_children):
        return DoubleColumnChartLine(self.pos_part, self.time_part)

    def visit_position_part(self, node, visited_children):
        self.pos_part = node.text

    def visit_timing_part(self, node, visited_children):
        _, time_part, _ = node.children
        self.time_part = time_part.text

    def generic_visit(self, node, visited_children):
        ...


def is_double_column_chart_line(line: str) -> bool:
    try:
        double_column_chart_line_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_double_column_chart_line(line: str) -> DoubleColumnChartLine:
    return DoubleColumnChartLineVisitor().visit(
        double_column_chart_line_grammar.parse(line)
    )


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
    encoded_line = line.encode("shift_jis_2004")
    if len(encoded_line) % 2 != 0:
        raise ValueError(f"Invalid chart line : {line}")
    symbols = []
    for i in range(0, len(encoded_line), 2):
        symbols.append(encoded_line[i : i + 2].decode("shift_jis_2004"))
    return symbols


def decimal_to_beats(decimal_time: Decimal) -> BeatsTime:
    return BeatsTime(decimal_time).limit_denominator(240)


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


def find_long_note_candidates(
    bloc: List[List[str]], note_symbols: Set[str], should_skip: Set[NotePosition]
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
        note_candidates: Set[Tuple[int, int]] = set()
        𝛿pos = LONG_DIRECTION[symbol]
        candidate = NotePosition(x, y) + 𝛿pos
        while 0 <= candidate.x < 4 and 0 <= candidate.y < 4:
            if candidate not in should_skip:
                new_symbol = bloc[candidate.y][candidate.x]
                if new_symbol in note_symbols:
                    note_candidates.add(candidate)
            candidate += 𝛿pos

        # if no notes have been crossed, we just ignore the arrow
        if note_candidates:
            arrow_to_note_candidates[pos] = note_candidates

    return arrow_to_note_candidates


def pick_correct_long_note_candidates(
    arrow_to_note_candidates: Dict[NotePosition, Set[NotePosition]],
    bloc: List[List[str]],
) -> Dict[NotePosition, NotePosition]:
    """Believe it or not, assigning each arrow to a valid note candidate
    involves whipping out a CSP solver.
    Returns an arrow_pos -> note_pos mapping
    """
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
    return abs(complex(*a.as_tuple()) - complex(*b.as_tuple()))


def long_note_solution_heuristic(
    solution: Dict[NotePosition, NotePosition]
) -> Tuple[int, int, int]:
    c = Counter(int(note_distance(k, v)) for k, v in solution.items())
    return (c[3], c[2], c[1])


def is_simple_solution(solution, domains) -> bool:
    return all(
        solution[v] == min(domains[v], key=lambda e: note_distance(e, v))
        for v in solution.keys()
    )


class JubeatAnalyserParser:
    def __init__(self):
        self.music = None
        self.symbols = deepcopy(SYMBOL_TO_DECIMAL_TIME)
        self.section_starting_beat = Decimal("0")
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

    def handle_command(self, command, value=None):
        try:
            method = getattr(self, f"do_{command}")
        except AttributeError:
            raise SyntaxError(f"Unknown analyser command : {command}") from None

        if value is not None:
            method(value)
        else:
            method()

    def do_b(self, value):
        self.beats_per_section = Decimal(value)

    def do_m(self, value):
        self.music = value

    def do_o(self, value):
        self.offset = int(value)

    def do_r(self, value):
        self.offset += int(value)

    def do_t(self, value):
        self.current_tempo = Decimal(value)
        self.timing_events.append(
            BPMEvent(self.section_starting_beat, BPM=self.current_tempo)
        )

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

    def _do_bpp(self, value):
        bpp = int(value)
        if bpp not in (1, 2):
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

    def is_short_line(self, line: str) -> bool:
        return len(line.encode("shift_jis_2004")) < self.bytes_per_panel * 4


@dataclass
class DoubleColumnFrame:
    position_part: List[List[str]]
    timing_part: List[List[str]]

    def __str__(self):
        res = []
        for pos, time in zip_longest(self.position_part, self.timing_part):
            line = [f"{''.join(pos)}"]
            if time is not None:
                line += [f"|{''.join(time)}|"]
            res += [" ".join(line)]
        return "\n".join(res)
