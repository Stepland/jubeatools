from collections import ChainMap, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from functools import partial
from io import StringIO
from itertools import chain
from typing import Dict, Iterator, List, Mapping, Optional, Tuple

from more_itertools import collapse, intersperse, mark_ends, windowed
from path import Path
from sortedcontainers import SortedKeyList

from jubeatools import __version__
from jubeatools.formats.filetypes import ChartFile, JubeatFile
from jubeatools.song import (
    BeatsTime,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    Song,
    TapNote,
    Timing,
)

from ..dump_tools import (
    BEATS_TIME_TO_SYMBOL,
    COMMAND_ORDER,
    DEFAULT_EXTRA_SYMBOLS,
    DIFFICULTIES,
    DIRECTION_TO_ARROW,
    DIRECTION_TO_LINE,
    JubeatAnalyserDumpedSection,
    LongNoteEnd,
    SortedDefaultDict,
    create_sections_from_chart,
    fraction_to_decimal,
    jubeat_analyser_file_dumper,
)
from ..symbols import CIRCLE_FREE_SYMBOLS, NOTE_SYMBOLS


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

    def _dump_notes(self, circle_free: bool = False,) -> Iterator[str]:
        frames: List[Dict[NotePosition, str]] = []
        frame: Dict[NotePosition, str] = {}
        for note in self.notes:
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
                        time_in_section = note.time - self.current_beat
                        symbol = self.symbols[time_in_section]
                        frame[pos] = symbol
                    elif is_last:
                        frame[pos] = arrow
                    else:
                        frame[pos] = line
            elif isinstance(note, TapNote):
                if note.position in frame:
                    frames.append(frame)
                    frame = {}
                time_in_section = note.time - self.current_beat
                symbol = self.symbols[time_in_section]
                frame[note.position] = symbol
            elif isinstance(note, LongNoteEnd):
                if note.position in frame:
                    frames.append(frame)
                    frame = {}
                time_in_section = note.time - self.current_beat
                if circle_free:
                    symbol = CIRCLE_FREE_SYMBOLS[time_in_section]
                else:
                    symbol = self.symbols[time_in_section]
                frame[note.position] = symbol

        frames.append(frame)
        dumped_frames = map(self._dump_frame, frames)
        yield from collapse(intersperse("", dumped_frames))

    @staticmethod
    def _dump_frame(frame: Dict[NotePosition, str]) -> Iterator[str]:
        for y in range(4):
            yield "".join(frame.get(NotePosition(x, y), "□") for x in range(4))


def _raise_if_unfit_for_mono_column(
    chart: Chart, timing: Timing, circle_free: bool = False
):
    if len(timing.events) < 1:
        raise ValueError("No BPM found in file") from None

    first_bpm = min(timing.events, key=lambda e: e.time)
    if first_bpm.time != 0:
        raise ValueError("First BPM event does not happen on beat zero")

    if any(
        not note.tail_is_straight()
        for note in chart.notes
        if isinstance(note, LongNote)
    ):
        raise ValueError(
            "Chart contains diagonal long notes, reprensenting these in"
            " mono_column format is not supported by jubeatools"
        )

    if circle_free and any(
        (note.time + note.duration) % BeatsTime(1, 4) != 0
        for note in chart.notes
        if isinstance(note, LongNote)
    ):
        raise ValueError(
            "Chart contains long notes whose ending timing aren't"
            " representable in #circlefree mode"
        )


def _dump_mono_column_chart(
    difficulty: str,
    chart: Chart,
    metadata: Metadata,
    timing: Timing,
    circle_free: bool = False,
) -> StringIO:

    _raise_if_unfit_for_mono_column(chart, timing, circle_free)

    sections = create_sections_from_chart(
        MonoColumnDumpedSection, chart, difficulty, timing, metadata, circle_free
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
    file.write(f"// https://github.com/Stepland/jubeatools\n\n")
    for _, section in sections.items():
        file.write(section.render(circle_free) + "\n")

    return file


def _dump_mono_column_internal(song: Song, circle_free: bool) -> List[ChartFile]:
    files: List[ChartFile] = []
    for difficulty, chart in song.charts.items():
        contents = _dump_mono_column_chart(
            difficulty,
            chart,
            song.metadata,
            chart.timing or song.global_timing,
            circle_free,
        )
        files.append(ChartFile(contents, song, difficulty, chart))

    return files


dump_mono_column = jubeat_analyser_file_dumper(_dump_mono_column_internal)
