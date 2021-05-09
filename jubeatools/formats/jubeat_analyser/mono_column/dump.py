from copy import deepcopy
from io import StringIO
from typing import Dict, Iterator, List

from more_itertools import collapse, intersperse, mark_ends

from jubeatools.song import (
    BeatsTime,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    TapNote,
    Timing,
)
from jubeatools.version import __version__

from ..dump_tools import (
    BEATS_TIME_TO_SYMBOL,
    DEFAULT_EXTRA_SYMBOLS,
    DIRECTION_TO_ARROW,
    DIRECTION_TO_LINE,
    NOTE_TO_CIRCLE_FREE_SYMBOL,
    JubeatAnalyserDumpedSection,
    LongNoteEnd,
    create_sections_from_chart,
    make_full_dumper_from_jubeat_analyser_chart_dumper,
)


class MonoColumnDumpedSection(JubeatAnalyserDumpedSection):
    def render(self, circle_free: bool = False) -> str:
        blocs = []
        commands = list(self._dump_commands())
        if commands:
            blocs.append(commands)
        symbols = list(self._dump_symbol_definitions())
        if symbols:
            blocs.append(symbols)
        notes = list(self._dump_notes(circle_free))
        if notes:
            blocs.append(notes)
        return "\n".join(collapse([intersperse("", blocs), "--"]))

    def _dump_notes(
        self,
        circle_free: bool = False,
    ) -> Iterator[str]:
        frames: List[Dict[NotePosition, str]] = []
        frame: Dict[NotePosition, str] = {}
        for note in self.notes:
            time_in_section = note.time - self.current_beat
            symbol = self.symbols[time_in_section]
            if isinstance(note, LongNote):
                needed_positions = set(note.positions_covered())
                if needed_positions & frame.keys():
                    frames.append(frame)
                    frame = {}
                direction = note.tail_direction()
                arrow = DIRECTION_TO_ARROW[direction]
                line = DIRECTION_TO_LINE[direction]
                for is_first, is_last, pos in mark_ends(note.positions_covered()):
                    if is_first:
                        frame[pos] = symbol
                    elif is_last:
                        frame[pos] = arrow
                    else:
                        frame[pos] = line
            elif isinstance(note, TapNote):
                if note.position in frame:
                    frames.append(frame)
                    frame = {}
                frame[note.position] = symbol
            elif isinstance(note, LongNoteEnd):
                if note.position in frame:
                    frames.append(frame)
                    frame = {}
                if circle_free and symbol in NOTE_TO_CIRCLE_FREE_SYMBOL:
                    symbol = NOTE_TO_CIRCLE_FREE_SYMBOL[symbol]
                frame[note.position] = symbol

        frames.append(frame)
        dumped_frames = map(self._dump_frame, frames)
        yield from collapse(intersperse("", dumped_frames))

    @staticmethod
    def _dump_frame(frame: Dict[NotePosition, str]) -> Iterator[str]:
        for y in range(4):
            yield "".join(frame.get(NotePosition(x, y), "□") for x in range(4))


def _raise_if_unfit_for_mono_column(chart: Chart, timing: Timing) -> None:
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
            " mono_column format is not supported by jubeatools"
        )


def _section_factory(b: BeatsTime) -> MonoColumnDumpedSection:
    return MonoColumnDumpedSection(current_beat=b)


def _dump_mono_column_chart(
    difficulty: str,
    chart: Chart,
    metadata: Metadata,
    timing: Timing,
    circle_free: bool = False,
) -> StringIO:

    _raise_if_unfit_for_mono_column(chart, timing)

    sections = create_sections_from_chart(
        _section_factory, chart, difficulty, timing, metadata, circle_free
    )

    # Define extra symbols
    existing_symbols = deepcopy(BEATS_TIME_TO_SYMBOL)
    extra_symbols = iter(DEFAULT_EXTRA_SYMBOLS)
    for section_start, section in sections.items():
        # intentionally not a copy : at the end of this loop every section
        # holds a reference to a dict containing every defined symbol
        section.symbols = existing_symbols
        for note in section.notes:
            time_in_section = note.time - section_start
            if time_in_section not in existing_symbols:
                new_symbol = next(extra_symbols)
                section.symbol_definitions[time_in_section] = new_symbol
                existing_symbols[time_in_section] = new_symbol

    # Actual output to file
    file = StringIO()
    file.write(f"// Converted using jubeatools {__version__}\n")
    file.write("// https://github.com/Stepland/jubeatools\n\n")
    for _, section in sections.items():
        file.write(section.render(circle_free) + "\n")

    return file


dump_mono_column = make_full_dumper_from_jubeat_analyser_chart_dumper(
    _dump_mono_column_chart
)
