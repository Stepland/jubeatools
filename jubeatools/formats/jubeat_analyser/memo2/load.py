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
from ..files import load_files
from ..load_tools import (
    CIRCLE_FREE_TO_DECIMAL_TIME,
    CIRCLE_FREE_TO_NOTE_SYMBOL,
    EMPTY_BEAT_SYMBOLS,
    LONG_ARROWS,
    LONG_DIRECTION,
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


@dataclass
class Notes:
    string: str

    def dump(self) -> str:
        return self.string


@dataclass
class Stop:
    duration: int

    def dump(self) -> str:
        return f"[{self.duration}]"


@dataclass
class BPM:
    value: Decimal

    def dump(self) -> str:
        return f"({self.value})"


Event = Union[Notes, Stop, BPM]


@dataclass
class RawMemo2ChartLine:
    position: str
    timing: Optional[List[Event]]

    def __str__(self):
        if self.timing:
            return f"{self.position} |{''.join(e.dump() for e in self.timing)}|"
        else:
            return self.position


@dataclass
class Memo2ChartLine:
    """timing part only contains notes"""

    position: str
    timing: Optional[List[str]]


memo2_chart_line_grammar = Grammar(
    r"""
    line            = ws position_part ws (timing_part ws)? comment?
    position_part   = ~r"[^*#:|/\s]{4,8}"
    timing_part     = "|" event+ "|"
    event           = stop / bpm / notes
    stop            = "[" pos_integer "]"
    pos_integer     = ~r"\d+"
    bpm             = "(" float ")"
    float           = ~r"\d+(\.\d+)?"
    notes           = ~r"[^*#:\(\[|/\s]+"
    ws              = ~r"[\t ]*"
    comment         = ~r"//.*"
"""
)


class Memo2ChartLineVisitor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.pos_part = None
        self.time_part = []

    def visit_line(self, node, visited_children):
        if not self.time_part:
            self.time_part = None
        return RawMemo2ChartLine(self.pos_part, self.time_part)

    def visit_position_part(self, node, visited_children):
        self.pos_part = node.text

    def visit_stop(self, node, visited_children):
        _, duration, _ = node.children
        self.time_part.append(Stop(int(duration.text)))

    def visit_bpm(self, node, visited_children):
        _, value, _ = node.children
        self.time_part.append(BPM(Decimal(value.text)))

    def visit_notes(self, node, visited_children):
        self.time_part.append(Notes(node.text))

    def generic_visit(self, node, visited_children):
        ...


def is_memo2_chart_line(line: str) -> bool:
    try:
        memo2_chart_line_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_memo2_chart_line(line: str) -> RawMemo2ChartLine:
    return Memo2ChartLineVisitor().visit(memo2_chart_line_grammar.parse(line))


@dataclass
class Memo2Frame:
    position_part: List[List[str]]
    timing_part: List[List[str]]

    @property
    def duration(self) -> BeatsTime:
        return BeatsTime(len(self.timing_part))

    def __str__(self):
        res = []
        for pos, time in zip_longest(self.position_part, self.timing_part):
            line = [f"{''.join(pos)}"]
            if time is not None:
                line += [f"|{''.join(time)}|"]
            res += [" ".join(line)]
        return "\n".join(res)


class Memo2Parser(JubeatAnalyserParser):
    def __init__(self):
        super().__init__()
        self.offset = None
        self.current_beat = BeatsTime(0)
        self.frames: List[Memo2Frame] = []

    def do_b(self, value):
        raise ValueError(
            "beat command (b=...) found, this commands cannot be used in #memo2 files"
        )

    def do_t(self, value):
        if self.frames:
            raise ValueError(
                "tempo command (t=...) found outside of the file header, "
                "this should not happen in #memo2 files"
            )
        else:
            self.timing_events.append(BPMEvent(self.current_beat, BPM=Decimal(value)))

    def do_r(self, value):
        if self.frames:
            raise ValueError(
                "offset increase command (r=...)  found outside of the file "
                "header, this is not supported by jubeatools"
            )
        elif self.offset is None:
            super().do_o(value)
        else:
            super().do_r(value)

    def do_memo(self):
        raise ValueError("#memo command found : This is not a memo2 file")

    def do_memo1(self):
        raise ValueError("#memo1 command found : This is not a memo2 file")

    def do_boogie(self):
        self.do_bpp(1)

    def do_memo2(self):
        ...

    def do_bpp(self, value):
        if self.frames:
            raise ValueError("jubeatools does not handle changes of #bpp halfway")
        else:
            self._do_bpp(value)

    def append_chart_line(self, raw_line: RawMemo2ChartLine):
        if len(raw_line.position.encode("shift-jis-2004")) != 4 * self.bytes_per_panel:
            raise SyntaxError(
                f"Invalid chart line for #bpp={self.bytes_per_panel} : {raw_line}"
            )
        if raw_line.timing is not None and self.bytes_per_panel == 2:
            if any(
                len(event.string.encode("shift-jis-2004")) % 2 != 0
                for event in raw_line.timing
                if isinstance(event, Notes)
            ):
                raise SyntaxError(f"Invalid chart line for #bpp=2 : {raw_line}")

        if not raw_line.timing:
            line = Memo2ChartLine(raw_line.position, None)
        else:
            # split notes
            bar = []
            for event in raw_line.timing:
                if isinstance(event, Notes):
                    bar.extend(self._split_chart_line(event.string))
                else:
                    bar.append(event)
            # extract timing info
            bar_length = sum(1 for e in bar if isinstance(e, str))
            symbol_duration = BeatsTime(1, bar_length)
            in_bar_beat = BeatsTime(0)
            for event in bar:
                if isinstance(event, str):
                    in_bar_beat += symbol_duration
                elif isinstance(event, BPM):
                    self.timing_events.append(
                        BPMEvent(time=self.current_beat + in_bar_beat, BPM=event.value)
                    )
                elif isinstance(event, Stop):
                    time = self.current_beat + in_bar_beat
                    if time != 0:
                        raise ValueError(
                            "Chart contains a pause that's not happening at the "
                            "very first beat, these are not supported by jubeatools"
                        )
                    if self.offset is None:
                        self.offset = event.duration
                    else:
                        # This could happen if several pauses exist at the first
                        # beat of the chart or if both an in-bar pause and an
                        # o=... command exist
                        self.offset += event.duration

            bar_notes = [e for e in bar if isinstance(e, str)]
            line = Memo2ChartLine(raw_line.position, bar_notes)

        self.current_chart_lines.append(line)
        if len(self.current_chart_lines) == 4:
            self._push_frame()

    def _split_chart_line(self, line: str) -> List[str]:
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
            memo_line.timing
            for memo_line in self.current_chart_lines
            if memo_line.timing is not None
        ]
        frame = Memo2Frame(position_part, timing_part)
        self.frames.append(frame)
        self.current_chart_lines = []

    def finish_last_few_notes(self):
        """Call this once when the end of the file is reached,
        flushes the chart line and chart frame buffers to create the last chart
        section"""
        if self.current_chart_lines:
            if len(self.current_chart_lines) != 4:
                raise SyntaxError(
                    f"Unfinished chart frame when flushing : \n"
                    f"{self.current_chart_lines}"
                )
            self._push_frame()

    def load_line(self, raw_line: str):
        line = raw_line.strip()
        if is_command(line):
            command, value = parse_command(line)
            self.handle_command(command, value)
        elif is_empty_line(line) or self.is_short_line(line):
            return
        elif is_memo2_chart_line(line):
            memo_chart_line = parse_memo2_chart_line(line)
            self.append_chart_line(memo_chart_line)
        else:
            raise SyntaxError(f"not a valid memo2 file line : {line}")

    def notes(self) -> Iterator[Union[TapNote, LongNote]]:
        if self.hold_by_arrow:
            yield from self._iter_notes()
        else:
            yield from self._iter_notes_without_longs()

    def _iter_frames(
        self,
    ) -> Iterator[Tuple[Mapping[str, BeatsTime], Memo2Frame, BeatsTime]]:
        """iterate over tuples of (currently_defined_symbols, frame)"""
        local_symbols: Dict[str, Decimal] = {}
        frame_starting_beat = BeatsTime(0)
        for i, frame in enumerate(self.frames):
            if frame.timing_part:
                frame_starting_beat = sum(f.duration for f in self.frames[:i])
                local_symbols = {
                    symbol: frame_starting_beat
                    + bar_index
                    + BeatsTime(symbol_index, len(bar))
                    for bar_index, bar in enumerate(frame.timing_part)
                    for symbol_index, symbol in enumerate(bar)
                    if symbol not in EMPTY_BEAT_SYMBOLS
                }
            yield local_symbols, frame

    def _iter_notes(self) -> Iterator[Union[TapNote, LongNote]]:
        unfinished_longs: Dict[NotePosition, UnfinishedLongNote] = {}
        for currently_defined_symbols, frame in self._iter_frames():
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
                            f"{frame}"
                        )
                else:
                    try:
                        symbol_time = currently_defined_symbols[symbol]
                    except KeyError:
                        continue

                should_skip.add(pos)
                yield unfinished_long.ends_at(symbol_time)

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
                    unfinished_longs[note_pos] = UnfinishedLongNote(
                        time=symbol_time, position=note_pos, tail_tip=arrow_pos
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
                yield TapNote(symbol_time, position)

    def _iter_notes_without_longs(self) -> Iterator[TapNote]:
        for currently_defined_symbols, frame in self._iter_frames():
            # cross compare symbols with the position information
            for y, x in product(range(4), range(4)):
                symbol = frame.position_part[y][x]
                try:
                    symbol_time = currently_defined_symbols[symbol]
                except KeyError:
                    continue
                position = NotePosition(x, y)
                yield TapNote(symbol_time, position)


def _load_memo2_file(lines: List[str]) -> Song:
    parser = Memo2Parser()
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


def load_memo2(path: Path) -> Song:
    files = load_files(path)
    charts = [_load_memo2_file(lines) for _, lines in files.items()]
    return reduce(Song.merge, charts)
