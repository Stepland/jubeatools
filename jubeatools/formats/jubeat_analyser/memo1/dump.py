from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from io import StringIO
from itertools import zip_longest
from math import ceil
from typing import Dict, Iterator, List, Union

from more_itertools import collapse, intersperse, mark_ends, windowed

from jubeatools.song import (
    BeatsTime,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    TapNote,
    Timing,
)
from jubeatools.utils import lcm
from jubeatools.version import __version__

from ..dump_tools import (
    DIRECTION_TO_ARROW,
    DIRECTION_TO_LINE,
    NOTE_TO_CIRCLE_FREE_SYMBOL,
    JubeatAnalyserDumpedSection,
    LongNoteEnd,
    create_sections_from_chart,
    make_full_dumper_from_jubeat_analyser_chart_dumper,
)
from ..symbols import NOTE_SYMBOLS

AnyNote = Union[TapNote, LongNote, LongNoteEnd]

EMPTY_BEAT_SYMBOL = "−"  # U+02212 : MINUS SIGN
EMPTY_POSITION_SYMBOL = "□"  # U+025A1 : WHITE SQUARE


@dataclass
class Frame:
    positions: Dict[NotePosition, str] = field(default_factory=dict)
    bars: Dict[int, List[str]] = field(default_factory=dict)

    def dump(self, length: BeatsTime) -> Iterator[str]:
        # Check that bars are contiguous
        for a, b in windowed(sorted(self.bars), 2):
            if a is not None and b is not None:
                if b - a != 1:
                    raise ValueError("Frame has discontinuous bars")
        # Check all bars are in the same 4-bar group
        if self.bars.keys() != set(bar % 4 for bar in self.bars):
            raise ValueError("Frame contains bars from different 4-bar groups")

        for pos, bar in zip_longest(self.dump_positions(), self.dump_bars(length)):
            if bar is None:
                bar = ""
            yield f"{pos} {bar}"

    def dump_positions(self) -> Iterator[str]:
        for y in range(4):
            yield "".join(
                self.positions.get(NotePosition(x, y), EMPTY_POSITION_SYMBOL)
                for x in range(4)
            )

    def dump_bars(self, length: BeatsTime) -> Iterator[str]:
        for i in range(ceil(length)):
            if i in self.bars:
                yield f"|{''.join(self.bars[i])}|"
            else:
                yield ""


class Memo1DumpedSection(JubeatAnalyserDumpedSection):
    def render(self, circle_free: bool = False) -> str:
        blocs = []
        commands = list(self._dump_commands())
        if commands:
            blocs.append(commands)
        notes = list(self._dump_notes(circle_free))
        if notes:
            blocs.append(notes)
        return "\n".join(collapse(intersperse("", blocs)))

    def _dump_notes(self, circle_free: bool = False) -> Iterator[str]:
        # Split notes into bars
        notes_by_bar: Dict[int, List[AnyNote]] = defaultdict(list)
        for note in self.notes:
            time_in_section = note.time - self.current_beat
            bar_index = int(time_in_section)
            notes_by_bar[bar_index].append(note)

        # Pre-render timing bars
        bars: Dict[int, List[str]] = defaultdict(list)
        chosen_symbols: Dict[BeatsTime, str] = {}
        symbols_iterator = iter(NOTE_SYMBOLS)
        for bar_index in range(ceil(self.length)):
            notes = notes_by_bar.get(bar_index, [])
            bar_length = lcm(
                *((note.time - self.current_beat).denominator for note in notes)
            )
            if bar_length < 3:
                bar_length = 4
            bar_dict: Dict[int, str] = {}
            for note in notes:
                time_in_section = note.time - self.current_beat
                time_in_bar = time_in_section % Fraction(1)
                time_index = time_in_bar.numerator * (
                    bar_length // time_in_bar.denominator
                )
                if time_index not in bar_dict:
                    symbol = next(symbols_iterator)
                    chosen_symbols[time_in_section] = symbol
                    bar_dict[time_index] = symbol
            bar = [bar_dict.get(i, EMPTY_BEAT_SYMBOL) for i in range(bar_length)]
            bars[bar_index] = bar

        # Create frame by bar
        frames_by_bar: Dict[int, List[Frame]] = defaultdict(list)
        for bar_index in range(ceil(self.length)):
            bar = bars.get(bar_index, [])
            frame = Frame()
            frame.bars[bar_index] = bar
            for note in notes_by_bar[bar_index]:
                time_in_section = note.time - self.current_beat
                symbol = chosen_symbols[time_in_section]
                if isinstance(note, TapNote):
                    if note.position in frame.positions:
                        frames_by_bar[bar_index].append(frame)
                        frame = Frame()
                    frame.positions[note.position] = symbol
                elif isinstance(note, LongNote):
                    needed_positions = set(note.positions_covered())
                    if needed_positions & frame.positions.keys():
                        frames_by_bar[bar_index].append(frame)
                        frame = Frame()
                    direction = note.tail_direction()
                    arrow = DIRECTION_TO_ARROW[direction]
                    line = DIRECTION_TO_LINE[direction]
                    for is_first, is_last, pos in mark_ends(note.positions_covered()):
                        if is_first:
                            frame.positions[pos] = symbol
                        elif is_last:
                            frame.positions[pos] = arrow
                        else:
                            frame.positions[pos] = line
                elif isinstance(note, LongNoteEnd):
                    if note.position in frame.positions:
                        frames_by_bar[bar_index].append(frame)
                        frame = Frame()
                    if circle_free and symbol in NOTE_TO_CIRCLE_FREE_SYMBOL:
                        symbol = NOTE_TO_CIRCLE_FREE_SYMBOL[symbol]
                    frame.positions[note.position] = symbol
            frames_by_bar[bar_index].append(frame)

        # Merge bar-specific frames is possible
        final_frames: List[Frame] = []
        for bar_index in range(ceil(self.length)):
            frames = frames_by_bar[bar_index]
            # Merge if :
            #  - No split in current bar (only one frame)
            #  - There is a previous frame
            #  - The previous frame is not a split frame (it holds a bar)
            #  - The previous and current bars are all in the same 4-bar group
            #  - The note positions in the previous frame do not clash with the current frame
            if (
                len(frames) == 1
                and final_frames
                and final_frames[-1].bars
                and max(final_frames[-1].bars.keys()) // 4
                == min(frames[0].bars.keys()) // 4
                and (
                    not (final_frames[-1].positions.keys() & frames[0].positions.keys())
                )
            ):
                final_frames[-1].bars.update(frames[0].bars)
                final_frames[-1].positions.update(frames[0].positions)
            else:
                final_frames.extend(frames)

        dumped_frames = map(lambda f: f.dump(self.length), final_frames)
        yield from collapse(intersperse("", dumped_frames))


def _raise_if_unfit_for_memo1(
    chart: Chart, timing: Timing, circle_free: bool = False
) -> None:
    if len(timing.events) < 1:
        raise ValueError("No BPM found in file") from None

    first_bpm = min(timing.events, key=lambda e: e.time)
    if first_bpm.time != 0:
        raise ValueError("First BPM event does not happen on beat zero")

    if any(
        not note.has_straight_tail()
        for note in chart.notes
        if isinstance(note, LongNote)
    ):
        raise ValueError(
            "Chart contains diagonal long notes, reprensenting these in"
            " memo format is not supported by jubeatools"
        )


def _section_factory(b: BeatsTime) -> Memo1DumpedSection:
    return Memo1DumpedSection(current_beat=b)


def _dump_memo1_chart(
    difficulty: str,
    chart: Chart,
    metadata: Metadata,
    timing: Timing,
    circle_free: bool = False,
) -> StringIO:

    _raise_if_unfit_for_memo1(chart, timing, circle_free)

    sections = create_sections_from_chart(
        Memo1DumpedSection, chart, difficulty, timing, metadata, circle_free
    )

    # Jubeat Analyser format command
    sections[BeatsTime(0)].commands["memo1"] = None

    # Actual output to file
    file = StringIO()
    file.write(f"// Converted using jubeatools {__version__}\n")
    file.write(f"// https://github.com/Stepland/jubeatools\n\n")
    file.write(
        "\n\n".join(section.render(circle_free) for _, section in sections.items())
    )

    return file


dump_memo1 = make_full_dumper_from_jubeat_analyser_chart_dumper(_dump_memo1_chart)
