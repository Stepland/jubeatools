from dataclasses import astuple, dataclass
from decimal import Decimal
from functools import reduce
from itertools import product, zip_longest
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Set, Tuple, Union

from parsimonious import Grammar, NodeVisitor, ParseError
from parsimonious.nodes import Node

from jubeatools.song import (
    BeatsTime,
    BPMEvent,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    Preview,
    SecondsTime,
    Song,
    TapNote,
    Timing,
)
from jubeatools.utils import none_or

from ..command import is_command, parse_command
from ..load_tools import (
    CIRCLE_FREE_TO_NOTE_SYMBOL,
    EMPTY_BEAT_SYMBOLS,
    JubeatAnalyserParser,
    UnfinishedLongNote,
    find_long_note_candidates,
    is_empty_line,
    load_folder,
    pick_correct_long_note_candidates,
)
from ..symbols import CIRCLE_FREE_SYMBOLS


@dataclass
class NoteCluster:
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


Event = Union[NoteCluster, Stop, BPM]


@dataclass
class RawMemo2ChartLine:
    position: str
    timing: Optional[List[Event]]

    def __str__(self) -> str:
        if self.timing:
            return f"{self.position} |{''.join(e.dump() for e in self.timing)}|"
        else:
            return self.position


@dataclass
class Memo2ChartLine:
    """timing part only contains notes"""

    position: str
    timing: Optional[List[str]]

    @property
    def duration(self) -> BeatsTime:
        if self.timing:
            return BeatsTime(1)
        else:
            return BeatsTime(0)


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
    ws              = ~r"[\t \u3000]*" # U+03000 : IDEOGRAPHIC SPACE
    comment         = ~r"//.*"
"""
)


class Memo2ChartLineVisitor(NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.pos_part: Optional[str] = None
        self.time_part: List[Union[NoteCluster, BPM, Stop]] = []

    def visit_line(self, node: Node, visited_children: list) -> RawMemo2ChartLine:
        if self.pos_part is None:
            raise ValueError("Line has no position part")

        return RawMemo2ChartLine(self.pos_part, self.time_part or None)

    def visit_position_part(self, node: Node, visited_children: list) -> None:
        self.pos_part = node.text

    def visit_stop(self, node: Node, visited_children: list) -> None:
        _, duration, _ = node.children
        self.time_part.append(Stop(int(duration.text)))

    def visit_bpm(self, node: Node, visited_children: list) -> None:
        _, value, _ = node.children
        self.time_part.append(BPM(Decimal(value.text)))

    def visit_notes(self, node: Node, visited_children: list) -> None:
        self.time_part.append(NoteCluster(node.text))

    def generic_visit(self, node: Node, visited_children: list) -> None:
        ...


def is_memo2_chart_line(line: str) -> bool:
    try:
        memo2_chart_line_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_memo2_chart_line(line: str) -> RawMemo2ChartLine:
    return Memo2ChartLineVisitor().visit(memo2_chart_line_grammar.parse(line))  # type: ignore


@dataclass
class Memo2Frame:
    position_part: List[List[str]]
    timing_part: List[List[str]]

    @property
    def duration(self) -> BeatsTime:
        return BeatsTime(len(self.timing_part))

    def __str__(self) -> str:
        res = []
        for pos, time in zip_longest(self.position_part, self.timing_part):
            line = [f"{''.join(pos)}"]
            if time is not None:
                line += [f"|{''.join(time)}|"]
            res += [" ".join(line)]
        return "\n".join(res)


class Memo2Parser(JubeatAnalyserParser):

    FORMAT_TAG = "#memo2"

    def __init__(self) -> None:
        super().__init__()
        self.current_chart_lines: List[Memo2ChartLine] = []
        self.frames: List[Memo2Frame] = []

    def do_b(self, value: str) -> None:
        if Decimal(value) != 4:
            raise RuntimeError(
                "Beat command (b=...) found with a value other that 4, this is "
                "unexpected in #memo2 files. If you are sure the file is not "
                "just actually a #memo1 or #memo file with the wrong format "
                "tag, you're welcome to report this error as a bug"
            )

    def do_t(self, value: str) -> None:
        self.timing_events.append(BPMEvent(self._current_beat(), BPM=Decimal(value)))

    def do_r(self, value: str) -> None:
        if self.frames:
            raise RuntimeError(
                "offset increase command (r=...)  found outside of the file "
                "header, this is not supported by jubeatools"
            )
        else:
            super().do_r(value)

    def do_boogie(self) -> None:
        self.do_bpp(1)

    def do_memo2(self) -> None:
        ...

    def do_bpp(self, value: Union[int, str]) -> None:
        if self.frames:
            raise RuntimeError("jubeatools does not handle changes of #bpp halfway")
        else:
            self._do_bpp(value)

    def append_chart_line(self, raw_line: RawMemo2ChartLine) -> None:
        if (
            len(raw_line.position.encode("shift-jis-2004", errors="surrogateescape"))
            != 4 * self.bytes_per_panel
        ):
            raise SyntaxError(
                f"Invalid chart line for #bpp={self.bytes_per_panel} : {raw_line}"
            )

        if raw_line.timing is not None and self.bytes_per_panel == 2:
            if any(
                len(e.string.encode("shift-jis-2004", errors="surrogateescape")) % 2
                != 0
                for e in raw_line.timing
                if isinstance(e, NoteCluster)
            ):
                raise SyntaxError(f"Invalid chart line for #bpp=2 : {raw_line}")

        if not raw_line.timing:
            line = Memo2ChartLine(raw_line.position, None)
        else:
            # split notes
            bar: List[Union[str, Stop, BPM]] = []
            for raw_event in raw_line.timing:
                if isinstance(raw_event, NoteCluster):
                    bar.extend(self._split_chart_line(raw_event.string))
                else:
                    bar.append(raw_event)
            # extract timing info
            bar_length = sum(1 for e in bar if isinstance(e, str))
            symbol_duration = BeatsTime(1, bar_length)
            in_bar_beat = BeatsTime(0)
            for event in bar:
                if isinstance(event, str):
                    in_bar_beat += symbol_duration
                elif isinstance(event, BPM):
                    self.timing_events.append(
                        BPMEvent(
                            time=self._current_beat() + in_bar_beat, BPM=event.value
                        )
                    )
                elif isinstance(event, Stop):
                    time = self._current_beat() + in_bar_beat
                    if time != 0:
                        raise ValueError(
                            "Chart contains a pause that's not happening at the "
                            "very first beat, these are not supported by jubeatools"
                        )
                    self.offset += event.duration

            bar_notes = [e for e in bar if isinstance(e, str)]
            line = Memo2ChartLine(raw_line.position, bar_notes)

        self.current_chart_lines.append(line)
        if len(self.current_chart_lines) == 4:
            self._push_frame()

    def _current_beat(self) -> BeatsTime:
        return self._frames_duration() + self._lines_duration()

    def _frames_duration(self) -> BeatsTime:
        return sum((frame.duration for frame in self.frames), start=BeatsTime(0))

    def _lines_duration(self) -> BeatsTime:
        return sum(
            (line.duration for line in self.current_chart_lines), start=BeatsTime(0)
        )

    def _push_frame(self) -> None:
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

    def finish_last_few_notes(self) -> None:
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

    def load_line(self, raw_line: str) -> None:
        line = raw_line.strip()
        self.raise_if_separator(line, self.FORMAT_TAG)
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
    ) -> Iterator[Tuple[Mapping[str, BeatsTime], Memo2Frame]]:
        """iterate over tuples of (currently_defined_symbols, frame)"""
        local_symbols = {}
        frame_starting_beat = BeatsTime(0)
        for i, frame in enumerate(self.frames):
            if frame.timing_part:
                frame_starting_beat = sum(
                    (f.duration for f in self.frames[:i]), start=BeatsTime(0)
                )
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
                x, y = astuple(pos)
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
                    arrow_to_note_candidates,
                    frame.position_part,
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
    for i, raw_line in enumerate(lines, start=1):
        try:
            parser.load_line(raw_line)
        except Exception as e:
            raise SyntaxError(f"On line {i}\n{e}")

    parser.finish_last_few_notes()
    metadata = Metadata(
        title=parser.title,
        artist=parser.artist,
        audio=none_or(Path, parser.music),
        cover=none_or(Path, parser.jacket),
    )
    if parser.preview_start is not None:
        metadata.preview = Preview(
            start=SecondsTime(parser.preview_start) / 1000, length=SecondsTime(10)
        )

    timing = Timing(
        events=parser.timing_events,
        beat_zero_offset=SecondsTime(parser.offset or 0) / 1000,
    )
    charts = {
        parser.difficulty
        or "EXT": Chart(
            level=Decimal(parser.level),
            timing=timing,
            notes=sorted(parser.notes(), key=lambda n: (n.time, n.position)),
        )
    }
    return Song(metadata=metadata, charts=charts)


def load_memo2(path: Path, **kwargs: Any) -> Song:
    files = load_folder(path)
    charts = [_load_memo2_file(lines) for _, lines in files.items()]
    return reduce(Song.merge, charts)
