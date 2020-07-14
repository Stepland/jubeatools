import warnings
from collections import ChainMap
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from functools import reduce
from itertools import chain, product
from typing import Mapping, Dict, Iterator, List, Optional, Set, Tuple, Union

import constraint
from parsimonious import Grammar, NodeVisitor, ParseError
from path import Path

from jubeatools.song import (
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
from ..parser import (
    CIRCLE_FREE_TO_DECIMAL_TIME,
    LONG_ARROWS,
    LONG_DIRECTION,
    JubeatAnalyserParser,
    UnfinishedLongNote,
    decimal_to_beats,
    is_empty_line,
    is_simple_solution,
    long_note_solution_heuristic,
    split_double_byte_line,
)
from ..symbol_definition import is_symbol_definition, parse_symbol_definition
from ..symbols import CIRCLE_FREE_SYMBOLS

memo_chart_line_grammar = Grammar(
    r"""
    line            = ws position_part ws (timing_part ws)? comment?
    position_part   = ~r"[^*#:|/\s]{4,8}"
    timing_part     = "|" ~r"[^*#:|/\s]+" "|"
    ws              = ~r"[\t ]*"
    comment         = ~r"//.*"
"""
)


@dataclass
class MemoChartLine:
    position: str
    timing: Optional[str]

    def __str__(self):
        return f"{self.position} |{self.timing}|"


class MemoChartLineVisitor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.pos_part = None
        self.time_part = None

    def visit_line(self, node, visited_children):
        return MemoChartLine(self.pos_part, self.time_part)

    def visit_position_part(self, node, visited_children):
        self.pos_part = node.text

    def visit_timing_part(self, node, visited_children):
        _, time_part, _ = node.children
        self.time_part = time_part.text

    def generic_visit(self, node, visited_children):
        ...


def is_memo_chart_line(line: str) -> bool:
    try:
        memo_chart_line_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_memo_chart_line(line: str) -> MemoChartLine:
    return MemoChartLineVisitor().visit(memo_chart_line_grammar.parse(line))


@dataclass
class MemoFrame:
    position_part: List[List[str]]
    timing_part: List[List[str]]

    @property
    def duration(self) -> Decimal:
        res = 0
        for t in self.timing_part:
            res += len(t)
        return Decimal("0.25") * res


@dataclass
class MemoLoadedSection:
    frames: List[MemoFrame]
    symbols: Dict[str, Decimal]
    length: Decimal
    tempo: Decimal


# Any unicode character that's both :
#  - confusable with a dash/hyphen
#  - encodable in shift_jis_2004
# Gets added to the list of characters to be ignored in the timing section
EMPTY_BEAT_SYMBOLS = {
    "一",  # U+04E00 - CJK UNIFIED IDEOGRAPH-4E00
    "－",  # U+0FF0D - FULLWIDTH HYPHEN-MINUS
    "ー",  # U+030FC - KATAKANA-HIRAGANA PROLONGED SOUND MARK
    "─",  # U+02500 - BOX DRAWINGS LIGHT HORIZONTAL
    "―",  # U+02015 - HORIZONTAL BAR
    "━",  # U+02501 - BOX DRAWINGS HEAVY HORIZONTAL
    "–",  # U+02013 - EN DASH
    "‐",  # U+02010 - HYPHEN
    "-",  # U+0002D - HYPHEN-MINUS
    "−",  # U+02212 - MINUS SIGN
}


class MemoParser(JubeatAnalyserParser):
    def __init__(self):
        super().__init__()
        self.symbols: Dict[str, Decimal] = {}
        self.frames: List[MemoFrame] = []
        self.sections: List[MemoLoadedSection] = []
        self.only_timingless_frames = False
    
    def do_memo(self):
        ...

    def do_memo1(self):
        raise ValueError("This is not a memo file")

    do_boogie = do_memo2 = do_memo1

    def do_bpp(self, value):
        if self.sections or self.frames:
            raise ValueError(
                "jubeatools does not handle changes of #bpp halfway"
            )
        else:
            self._do_bpp(value)

    def append_chart_line(self, line: MemoChartLine):
        if len(line.position.encode("shift_jis_2004")) != 4 * self.bytes_per_panel:
            raise SyntaxError(f"Invalid chart line for #bpp={self.bytes_per_panel} : {line}")
        if line.timing is not None and self.bytes_per_panel == 2:
            if len(line.timing.encode("shift_jis_2004")) % 2 != 0:
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
        frame = MemoFrame(position_part, timing_part)
        # if the current frame has some timing info
        if frame.duration > 0:
            # and the previous frames already cover enough beats
            if self._frames_duration() >= self.beats_per_section:
                # then the current frame starts a new section
                self._push_section()
        
        self.frames.append(frame)

    def _push_section(self):
        self.sections.append(
            MemoLoadedSection(
                frames=deepcopy(self.frames),
                symbols=deepcopy(self.symbols),
                length=self.beats_per_section,
                tempo=self.current_tempo,
            )
        )
        self.frames = []
        self.current_chart_lines = []
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
        elif is_symbol_definition(line):
            symbol, timing = parse_symbol_definition(line)
            self.define_symbol(symbol, timing)
        elif is_memo_chart_line(line):
            memo_chart_line = parse_memo_chart_line(line)
            self.append_chart_line(memo_chart_line)
        elif not (is_empty_line(line) or self.is_short_line(line)):
            raise SyntaxError(f"not a valid mono-column file line : {line}")

    def notes(self) -> Iterator[Union[TapNote, LongNote]]:
        if self.hold_by_arrow:
            yield from self._iter_notes()
        else:
            yield from self._iter_notes_without_longs()
    
    def _iter_frames(self) -> Iterator[Tuple[Decimal, Mapping[str, Decimal], MemoLoadedSection]]:
        """iterate over tuples of frame_starting_beat, frame, section_starting_beat, section"""
        section_starting_beat = Decimal(0)
        for section in self.sections:
            frame_starting_beat = Decimal(0)
            for frame in section.frames:
                yield frame_starting_beat, frame, section_starting_beat, section
                frame_starting_beat += frame.duration
            section_starting_beat += section.length

    def _iter_notes(self) -> Iterator[Union[TapNote, LongNote]]:
        unfinished_longs: Dict[NotePosition, UnfinishedLongNote] = {}
        for section_starting_beat, section, bloc in self._iter_blocs():
            should_skip: Set[NotePosition] = set()

            # 1/3 : look for ends to unfinished long notes
            for pos, unfinished_long in unfinished_longs.items():
                x, y = pos.as_tuple()
                symbol = bloc[y][x]
                if self.circle_free:
                    if symbol in CIRCLE_FREE_SYMBOLS:
                        should_skip.add(pos)
                        symbol_time = CIRCLE_FREE_TO_DECIMAL_TIME[symbol]
                        note_time = decimal_to_beats(section_starting_beat + symbol_time)
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
                        note_time = decimal_to_beats(section_starting_beat + symbol_time)
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
                for arrow_pos, note_pos in solution.items():
                    should_skip.add(arrow_pos)
                    should_skip.add(note_pos)
                    symbol = bloc[note_pos.y][note_pos.x]
                    symbol_time = section.symbols[symbol]
                    note_time = decimal_to_beats(section_starting_beat + symbol_time)
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
                    note_time = decimal_to_beats(section_starting_beat + symbol_time)
                    yield TapNote(note_time, position)

    def _iter_notes_without_longs(self) -> Iterator[TapNote]:
        local_symbols: Dict[str, Decimal] = {}
        for frame_starting_beat, frame, section_starting_beat, section in self._iter_frames():
            # define local note symbols according to what's found in the timing part
            if frame.timing_part:
                local_symbols = {
                    symbol: Decimal("0.25") * i
                    for i, symbol in enumerate(chain(frame.timing_part))
                    if symbol not in EMPTY_BEAT_SYMBOLS
                }
            currently_defined_symbols = ChainMap(local_symbols, section.symbols)
            # cross compare with the position information
            for y, x in product(range(4), range(4)):
                symbol = frame.position_part[y][x]
                try:
                    symbol_time = currently_defined_symbols[symbol]
                except KeyError:
                    continue
                note_time = decimal_to_beats(section_starting_beat + frame_starting_beat + symbol_time)
                position = NotePosition(x, y)
                yield TapNote(note_time, position)


def _load_memo_file(lines: List[str]) -> Song:
    parser = MemoParser()
    for i, raw_line in enumerate(lines):
        try:
            parser.load_line(raw_line)
        except Exception as e:
            raise SyntaxError(
                f"Error while parsing memo line {i} :\n" f"{type(e).__name__}: {e}"
            ) from None

    # finish the current section
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


def load_memo(path: Path) -> Song:
    files = load_files(path)
    charts = [_load_memo_file(lines) for _, lines in files.items()]
    return reduce(lambda a, b: a.merge(b), charts)
