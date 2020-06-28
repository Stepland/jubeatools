from collections import ChainMap, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from io import StringIO
from itertools import chain
from typing import IO, Dict, Iterator, List, Optional, Tuple

from more_itertools import collapse, intersperse, windowed
from sortedcontainers import SortedKeyList, SortedSet

from jubeatools import __version__
from jubeatools.song import BeatsTime, Chart, LongNote, Metadata, Song, TapNote, Timing

from ..command import dump_command


def dump_mono_column(song: Song) -> Dict[str, IO]:
    files = {}
    for difname, chart in song.charts.items():
        filename = f"{song.metadata.title} [{difname}].txt"
        files[filename] = _dump_mono_column_chart(
            difname, chart, song.metadata, chart.timing or song.global_timing,
        )
    return files


def _raise_if_unfit_for_mono_column(chart: Chart, timing: Timing):
    if any(isinstance(note, LongNote) for note in chart.notes):
        raise ValueError(
            "Long notes aren't currently supported when dumping to mono-column"
        )

    if len(timing.event) < 1:
        raise ValueError("No BPM found in file") from None

    first_bpm = min(timing.events, key=lambda e: e.time)
    if first_bpm.time != 0:
        raise ValueError("First BPM event does not happen on beat zero")


COMMAND_ORDER = SortedSet(
    ["b", "t", "m", "o", "r", "title", "artist", "lev", "dif", "jacket", "prevpos"]
)


BEATS_TIME_TO_SYMBOL = {
    BeatsTime(1, 4) * index: symbol for index, symbol in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯")
}


def fraction_to_decimal(frac: Fraction):
    "Thanks stackoverflow ! https://stackoverflow.com/a/40468867/10768117"
    return frac.numerator / Decimal(frac.denominator)


@dataclass
class MonoColumnDumpedSection:
    commands: Dict[str, Optional[str]] = field(default_factory=dict)
    extra_symbols: Dict[BeatsTime, str] = field(default_factory=dict)
    notes: List[TapNote] = field(default_factory=list)

    def __str__(self) -> str:
        blocs = []
        commands = list(self._dump_commands())
        if commands:
            blocs.append(commands)
        symbols = list(self._dump_extra_symbols())
        if symbols:
            blocs.append(symbols)
        notes = list(self._dump_notes())
        if notes:
            blocs.append(notes)
        return "\n".join(collapse([intersperse("", blocs), "--"]))

    def _dump_commands(self) -> Iterator[str]:
        keys = chain(COMMAND_ORDER, self.commands.keys() - COMMAND_ORDER)
        for key in keys:
            try:
                value = self.commands[key]
            except KeyError:
                continue
            yield dump_command(key, value)

    def _dump_extra_symbols(self) -> Iterator[str]:
        for time, symbol in self.extra_symbols.items():
            decimal_time = fraction_to_decimal(time)
            yield f"*{symbol}:{decimal_time:.6f}"

    def _dump_notes(self) -> Iterator[str]:
        frames: List[Dict[Tuple[int, int], str]] = []
        frame: Dict[Tuple[int, int], str] = {}
        symbols: Dict[BeatsTime, str] = ChainMap(
            BEATS_TIME_TO_SYMBOL, self.extra_symbols
        )
        for note in self.notes:
            pos = note.position.as_tuple()
            if pos in frame:
                frames.append(frame)
                frame = {}
            symbol = symbols[note.time]
            frame[pos] = symbol
        frames.append(frame)
        dumped_frames = map(self._dump_frame, frames)
        yield from collapse(intersperse("", dumped_frames))

    @staticmethod
    def _dump_frame(frame: Dict[Tuple[int, int], str]) -> Iterator[str]:
        for y in range(4):
            yield "".join(frame.get((x, y), "□") for x in range(4))


DIFFICULTIES = {"BSC": 1, "ADV": 2, "EXT": 3}

DEFAULT_EXTRA_SYMBOLS = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ" "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"


def _dump_mono_column_chart(
    difficulty: str, chart: Chart, metadata: Metadata, timing: Timing
) -> IO:

    _raise_if_unfit_for_mono_column(chart, timing)

    timing_events = sorted(timing.events, key=lambda e: e.time)
    notes = SortedKeyList(set(chart.notes), key=lambda n: n.time)
    last_event_time = max(timing_events[-1].time, notes[-1].time)
    last_measure = last_event_time // 4
    sections = defaultdict(
        MonoColumnDumpedSection,
        {BeatsTime(4) * i: MonoColumnDumpedSection() for i in range(last_measure + 1)},
    )
    sections[0].commands.update(
        o=int(timing.beat_zero_offset * 1000),
        m=metadata.audio,
        title=metadata.title,
        artist=metadata.artist,
        lev=int(chart.level),
        dif=DIFFICULTIES.get(difficulty, 1),
        jacket=metadata.cover,
        prevpos=int(metadata.preview_start * 1000),
    )
    # Potentially create sub-sections for bpm changes
    for event in timing_events:
        sections[event.time].commands["t"] = event.BPM
    # Frist, Set every single b=... value
    section_starts = sorted(sections.keys())
    for key, next_key in windowed(section_starts + [None], 2):
        if next_key is None:
            sections[key].commands["b"] = 4
        else:
            sections[key].commands["b"] = fraction_to_decimal(next_key - key)
    # Then, trim all the redundant b=...
    last_b = 4
    for key in section_starts:
        current_b = sections[key].commands["b"]
        if current_b == last_b:
            del sections[key].commands["b"]
        else:
            last_b = current_b
    # Fill sections with notes
    for key, next_key in windowed(section_starts + [None], 2):
        sections[key].notes = list(
            notes.irange_key(min_key=key, max_key=next_key, inclusive=(True, False))
        )
    # Define extra symbols
    existing_symbols = {
        BeatsTime(1, 4) * index: symbol
        for index, symbol in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯")
    }
    extra_symbols = iter(DEFAULT_EXTRA_SYMBOLS)
    for section_start in section_starts:
        section = sections[section_start]
        for note in section.notes:
            time_in_section = note.time - section_start
            if time_in_section not in existing_symbols:
                section.extra_symbols[note.time] = next(extra_symbols)

    # Actual output to file
    file = StringIO()
    file.write(f"// Converted using jubeatools {__version__}\n")
    file.write(f"// https://github.com/Stepland/jubeatools\n\n")
    for key in section_starts:
        section = sections[key]
        file.write(str(section) + "\n")

    return file
