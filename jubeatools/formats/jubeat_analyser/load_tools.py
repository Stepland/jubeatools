"""Collection of parsing tools that are common to all the jubeat analyser formats"""
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Tuple

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


def is_empty_line(line: str) -> bool:
    return bool(EMPTY_LINE.match(line))


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

    def do_m(self, value):
        self.music = value

    def do_t(self, value):
        self.current_tempo = Decimal(value)
        self.timing_events.append(
            BPMEvent(self.section_starting_beat, BPM=self.current_tempo)
        )

    def do_o(self, value):
        self.offset = int(value)

    def do_b(self, value):
        self.beats_per_section = Decimal(value)

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
