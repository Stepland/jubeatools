from decimal import Decimal
from pathlib import Path
from typing import List, Set, Union

import hypothesis.strategies as st
from hypothesis import given

from jubeatools.song import (
    BeatsTime,
    BPMEvent,
    Chart,
    LongNote,
    Metadata,
    SecondsTime,
    TapNote,
    Timing,
)
from jubeatools.testutils.strategies import NoteOption, long_note
from jubeatools.testutils.strategies import notes as notes_strat
from jubeatools.testutils.strategies import tap_note

from ..mono_column.dump import _dump_mono_column_chart
from ..mono_column.load import MonoColumnParser


@given(st.sets(tap_note(), min_size=1, max_size=100))
def test_tap_notes(notes: Set[TapNote]) -> None:
    timing = Timing(
        events=[BPMEvent(BeatsTime(0), Decimal(120))], beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(
        level=Decimal(0),
        timing=timing,
        notes=sorted(notes, key=lambda n: (n.time, n.position)),
    )
    metadata = Metadata("", "", Path(""), Path(""))
    string_io = _dump_mono_column_chart("", chart, metadata, timing)
    chart_text = string_io.getvalue()
    parser = MonoColumnParser()
    for line in chart_text.split("\n"):
        parser.load_line(line)
    actual = set(parser.notes())
    assert notes == actual


@given(long_note())
def test_single_long_note(note: LongNote) -> None:
    timing = Timing(
        events=[BPMEvent(BeatsTime(0), Decimal(120))], beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(level=Decimal(0), timing=timing, notes=[note])
    metadata = Metadata("", "", Path(""), Path(""))
    string_io = _dump_mono_column_chart("", chart, metadata, timing)
    chart_text = string_io.getvalue()
    parser = MonoColumnParser()
    for line in chart_text.split("\n"):
        parser.load_line(line)
    actual = set(parser.notes())
    assert set([note]) == actual


@given(notes_strat(NoteOption.LONGS))
def test_many_notes(notes: List[Union[TapNote, LongNote]]) -> None:
    timing = Timing(
        events=[BPMEvent(BeatsTime(0), Decimal(120))], beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(
        level=Decimal(0),
        timing=timing,
        notes=sorted(notes, key=lambda n: (n.time, n.position)),
    )
    metadata = Metadata("", "", Path(""), Path(""))
    string_io = _dump_mono_column_chart("", chart, metadata, timing)
    chart_text = string_io.getvalue()
    parser = MonoColumnParser()
    for line in chart_text.split("\n"):
        parser.load_line(line)
    actual = set(parser.notes())
    assert notes == actual
