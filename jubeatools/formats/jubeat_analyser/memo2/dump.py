from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from io import StringIO
from itertools import chain, zip_longest
from typing import Dict, Iterator, List, Optional, Union

from more_itertools import collapse, intersperse, mark_ends, windowed
from sortedcontainers import SortedKeyList

from jubeatools.song import (
    BeatsTime,
    BPMEvent,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    SecondsTime,
    TapNote,
    Timing,
)
from jubeatools.utils import lcm
from jubeatools.version import __version__

from ..command import dump_command
from ..dump_tools import (
    DIFFICULTY_NUMBER,
    DIRECTION_TO_ARROW,
    DIRECTION_TO_LINE,
    NOTE_TO_CIRCLE_FREE_SYMBOL,
    LongNoteEnd,
    SortedDefaultDict,
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

    def dump(self) -> Iterator[str]:
        # Check that bars are contiguous
        for a, b in windowed(sorted(self.bars), 2):
            if a is not None and b is not None:
                if b - a != 1:
                    raise ValueError("Frame has discontinuous bars")

        for pos, bar in zip_longest(self.dump_positions(), self.dump_bars()):
            if bar is None:
                yield pos
            else:
                yield f"{pos} {bar}"

    def dump_positions(self) -> Iterator[str]:
        for y in range(4):
            yield "".join(
                self.positions.get(NotePosition(x, y), EMPTY_POSITION_SYMBOL)
                for x in range(4)
            )

    def dump_bars(self) -> Iterator[str]:
        for i in range(4):
            if i in self.bars:
                yield f"|{''.join(self.bars[i])}|"
            else:
                yield ""


@dataclass
class StopEvent:
    time: BeatsTime
    duration: SecondsTime


@dataclass
class BarEvent:
    note: Optional[str] = None
    bpms: List[BPMEvent] = field(default_factory=list)
    stops: List[StopEvent] = field(default_factory=list)


@dataclass
class Memo2Section:
    """A 4-beat-long group of notes"""

    notes: List[AnyNote] = field(default_factory=list)
    events: List[Union[BPMEvent, StopEvent]] = field(default_factory=list)

    def render(self, circle_free: bool = False) -> str:
        return "\n".join(self._dump_notes(circle_free))

    def _dump_notes(self, circle_free: bool = False) -> Iterator[str]:
        # Split notes and events into bars
        notes_by_bar: Dict[int, List[AnyNote]] = defaultdict(list)
        for note in self.notes:
            time_in_section = note.time % BeatsTime(4)
            bar_index = int(time_in_section)
            notes_by_bar[bar_index].append(note)
        events_by_bar: Dict[int, List[Union[BPMEvent, StopEvent]]] = defaultdict(list)
        for event in self.events:
            time_in_section = event.time % BeatsTime(4)
            bar_index = int(time_in_section)
            events_by_bar[bar_index].append(event)

        # Pre-render timing bars
        bars: Dict[int, List[str]] = defaultdict(list)
        chosen_symbols: Dict[BeatsTime, str] = {}
        symbols_iterator = iter(NOTE_SYMBOLS)
        for bar_index in range(4):
            notes = notes_by_bar.get(bar_index, [])
            events = events_by_bar.get(bar_index, [])
            bar_length = lcm(
                *(
                    [note.time.denominator for note in notes]
                    + [event.time.denominator for event in events]
                )
            )
            if bar_length < 3:
                bar_length = 4

            bar_dict: Dict[int, BarEvent] = defaultdict(BarEvent)
            for note in notes:
                time_in_section = note.time % BeatsTime(4)
                time_in_bar = note.time % Fraction(1)
                time_index = time_in_bar.numerator * (
                    bar_length // time_in_bar.denominator
                )
                if time_index not in bar_dict:
                    symbol = next(symbols_iterator)
                    chosen_symbols[time_in_section] = symbol
                    bar_dict[time_index].note = symbol

            for event in events:
                time_in_bar = event.time % Fraction(1)
                time_index = time_in_bar.numerator * (
                    bar_length // time_in_bar.denominator
                )
                if isinstance(event, StopEvent):
                    bar_dict[time_index].stops.append(event)
                elif isinstance(event, BPMEvent):
                    bar_dict[time_index].bpms.append(event)

            bar = []
            for i in range(bar_length):
                bar_event = bar_dict.get(i, BarEvent())
                for stop in bar_event.stops:
                    bar.append(f"[{int(stop.duration * 1000)}]")

                for bpm in bar_event.bpms:
                    bar.append(f"({bpm.BPM})")

                bar.append(bar_event.note or EMPTY_BEAT_SYMBOL)

            bars[bar_index] = bar

        # Create frame by bar
        frames_by_bar: Dict[int, List[Frame]] = defaultdict(list)
        for bar_index in range(4):
            bar = bars.get(bar_index, [])
            frame = Frame()
            frame.bars[bar_index] = bar
            for note in notes_by_bar[bar_index]:
                time_in_section = note.time % BeatsTime(4)
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
        for bar_index in range(4):
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

        dumped_frames = map(lambda f: f.dump(), final_frames)
        yield from collapse(intersperse("", dumped_frames))


def _raise_if_unfit_for_memo2(
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


def _dump_memo2_chart(
    difficulty: str,
    chart: Chart,
    metadata: Metadata,
    timing: Timing,
    circle_free: bool = False,
) -> StringIO:

    _raise_if_unfit_for_memo2(chart, timing, circle_free)

    def make_section(b: BeatsTime) -> Memo2Section:
        return Memo2Section()

    sections = SortedDefaultDict(make_section)

    timing_events = sorted(timing.events, key=lambda e: e.time)
    notes = SortedKeyList(set(chart.notes), key=lambda n: n.time)

    for note in chart.notes:
        if isinstance(note, LongNote):
            notes.add(LongNoteEnd(note.time + note.duration, note.position))

    all_events = SortedKeyList(timing_events + notes, key=lambda n: n.time)
    last_event = all_events[-1]
    last_measure = last_event.time // 4
    for i in range(last_measure + 1):
        beat = BeatsTime(4) * i
        sections.add_key(beat)

    # Timing events
    sections[BeatsTime(0)].events.append(
        StopEvent(BeatsTime(0), timing.beat_zero_offset)
    )
    for event in timing_events:
        section_beat = event.time - (event.time % 4)
        sections[section_beat].events.append(event)

    # Fill sections with notes
    for key, next_key in windowed(chain(sections.keys(), [None]), 2):
        assert key is not None
        sections[key].notes = list(
            notes.irange_key(min_key=key, max_key=next_key, inclusive=(True, False))
        )

    # Actual output to file
    file = StringIO()
    file.write(f"// Converted using jubeatools {__version__}\n")
    file.write(f"// https://github.com/Stepland/jubeatools\n\n")

    # Header
    file.write(dump_command("lev", Decimal(chart.level)) + "\n")
    file.write(dump_command("dif", DIFFICULTY_NUMBER.get(difficulty, 1)) + "\n")
    if metadata.audio is not None:
        file.write(dump_command("m", metadata.audio) + "\n")
    if metadata.title is not None:
        file.write(dump_command("title", metadata.title) + "\n")
    if metadata.artist is not None:
        file.write(dump_command("artist", metadata.artist) + "\n")
    if metadata.cover is not None:
        file.write(dump_command("jacket", metadata.cover) + "\n")
    if metadata.preview is not None:
        file.write(dump_command("prevpos", int(metadata.preview.start * 1000)) + "\n")

    if any(isinstance(note, LongNote) for note in chart.notes):
        file.write(dump_command("holdbyarrow", 1) + "\n")

    if circle_free:
        file.write(dump_command("circlefree", 1) + "\n")

    file.write(dump_command("memo2") + "\n")

    file.write("\n")

    # Notes
    file.write(
        "\n\n".join(section.render(circle_free) for _, section in sections.items())
    )

    return file


dump_memo2 = make_full_dumper_from_jubeat_analyser_chart_dumper(_dump_memo2_chart)
