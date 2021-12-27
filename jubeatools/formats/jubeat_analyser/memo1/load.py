from copy import deepcopy
from dataclasses import astuple, dataclass
from decimal import Decimal
from itertools import product
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Set, Tuple, Union

from more_itertools import mark_ends

from jubeatools.song import (
    BeatsTime,
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
    DoubleColumnChartLine,
    DoubleColumnFrame,
    JubeatAnalyserParser,
    UnfinishedLongNote,
    find_long_note_candidates,
    is_double_column_chart_line,
    is_empty_line,
    load_folder,
    parse_double_column_chart_line,
    pick_correct_long_note_candidates,
)
from ..symbols import CIRCLE_FREE_SYMBOLS


class Memo1Frame(DoubleColumnFrame):
    @property
    def duration(self) -> BeatsTime:
        # This is wrong for the last frame in a section if the section has a
        # length in beats that's not an integer
        return BeatsTime(len(self.timing_part))


@dataclass
class Memo1LoadedSection:
    frames: List[Memo1Frame]
    length: BeatsTime
    tempo: Decimal

    def __str__(self) -> str:
        res = []
        if self.length != 4:
            res += [f"b={self.length}", ""]
        for _, is_last, frame in mark_ends(self.frames):
            res += [str(frame)]
            if not is_last:
                res += [""]
        return "\n".join(res)


class Memo1Parser(JubeatAnalyserParser):

    FORMAT_TAG = "#memo1"

    def __init__(self) -> None:
        super().__init__()
        self.current_chart_lines: List[DoubleColumnChartLine] = []
        self.current_frames: List[Memo1Frame] = []
        self.sections: List[Memo1LoadedSection] = []

    def do_memo1(self) -> None:
        ...

    def do_b(self, value: str) -> None:
        """Because of the way the parser works,
        b= commands must mark the end of a section to be properly taken into
        account"""
        if self.current_chart_lines:
            raise SyntaxError("Found a b= command before the end of a frame")
        if self.current_frames and self._frames_duration() < self.beats_per_section:
            raise SyntaxError("Found a b= command before the end of a section")

        self._push_section()
        super().do_b(value)

    def do_bpp(self, value: str) -> None:
        if self.sections or self.current_frames:
            raise ValueError("jubeatools does not handle changes of #bpp halfway")
        else:
            self._do_bpp(value)

    def append_chart_line(self, line: DoubleColumnChartLine) -> None:
        line.raise_if_unfit(self.bytes_per_panel)
        self.current_chart_lines.append(line)
        if len(self.current_chart_lines) == 4:
            self._push_frame()

    def _frames_duration(self) -> BeatsTime:
        return sum(
            (frame.duration for frame in self.current_frames), start=BeatsTime(0)
        )

    def _current_beat(self) -> BeatsTime:
        # If we've already seen enough beats, we need to circumvent the wrong
        # duration computation
        if self._frames_duration() >= self.beats_per_section:
            frames_duration = self.beats_per_section
        else:
            frames_duration = self._frames_duration()

        return self.section_starting_beat + frames_duration

    def _push_frame(self) -> None:
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

        self.current_frames.append(frame)
        self.current_chart_lines = []

    def _push_section(self) -> None:
        """Take all currently stacked frames and push them to a new section,
        Move time forward by the number of beats per section"""
        if not self.current_frames:
            raise RuntimeError(
                "Tried pushing a new section but no frames are currently stacked"
            )
        self.sections.append(
            Memo1LoadedSection(
                frames=deepcopy(self.current_frames),
                length=self.beats_per_section,
                tempo=self.current_tempo,
            )
        )
        self.current_frames = []
        self.section_starting_beat += self.beats_per_section

    def finish_last_few_notes(self) -> None:
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

    def load_line(self, raw_line: str) -> None:
        line = raw_line.strip()
        self.raise_if_separator(line, self.FORMAT_TAG)
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
        Tuple[Mapping[str, BeatsTime], Memo1Frame, BeatsTime, Memo1LoadedSection]
    ]:
        """iterate over tuples of
        currently_defined_symbols, frame, section_starting_beat, section"""
        local_symbols = {}
        section_starting_beat = BeatsTime(0)
        for section in self.sections:
            frame_starting_beat = BeatsTime(0)
            for i, frame in enumerate(section.frames):
                if frame.timing_part:
                    frame_starting_beat = sum(
                        (f.duration for f in section.frames[:i]), start=BeatsTime(0)
                    )
                    local_symbols = {
                        symbol: BeatsTime(symbol_index, len(bar))
                        + bar_index
                        + frame_starting_beat
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
                            f"{section}"
                        )
                else:
                    try:
                        symbol_time = currently_defined_symbols[symbol]
                    except KeyError:
                        continue

                should_skip.add(pos)
                note_time = section_starting_beat + symbol_time
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
                    arrow_to_note_candidates,
                    frame.position_part,
                )
                for arrow_pos, note_pos in solution.items():
                    should_skip.add(arrow_pos)
                    should_skip.add(note_pos)
                    symbol = frame.position_part[note_pos.y][note_pos.x]
                    symbol_time = currently_defined_symbols[symbol]
                    note_time = section_starting_beat + symbol_time
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
                note_time = section_starting_beat + symbol_time
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
                note_time = section_starting_beat + symbol_time
                position = NotePosition(x, y)
                yield TapNote(note_time, position)


def _load_memo1_file(lines: List[str]) -> Song:
    parser = Memo1Parser()
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
        events=parser.timing_events, beat_zero_offset=SecondsTime(parser.offset) / 1000
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


def load_memo1(path: Path, **kwargs: Any) -> Song:
    files = load_folder(path)
    charts = [_load_memo1_file(lines) for _, lines in files.items()]
    return Song.from_monochart_instances(*charts)
