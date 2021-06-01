from decimal import Decimal
from pathlib import Path
from typing import List, Set, Union

import hypothesis.strategies as st
from hypothesis import given

from jubeatools.formats import Format
from jubeatools.formats.jubeat_analyser.mono_column.dump import _dump_mono_column_chart
from jubeatools.formats.jubeat_analyser.mono_column.load import MonoColumnParser
from jubeatools.song import (
    BeatsTime,
    BPMEvent,
    Chart,
    LongNote,
    Metadata,
    SecondsTime,
    Song,
    TapNote,
    Timing,
)
from jubeatools.testutils.strategies import long_note
from jubeatools.testutils.strategies import notes as notes_strat
from jubeatools.testutils.strategies import tap_note
from jubeatools.testutils.test_patterns import dump_and_load_then_compare

from ..test_utils import memo_compatible_song


@given(st.sets(tap_note(), min_size=1, max_size=100))
def test_that_a_set_of_tap_notes_roundtrip(notes: Set[TapNote]) -> None:
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
def test_that_a_single_long_note_roundtrips(note: LongNote) -> None:
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


@given(notes_strat())
def test_that_many_notes_roundtrip(notes: List[Union[TapNote, LongNote]]) -> None:
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


@given(memo_compatible_song(), st.booleans())
def test_that_full_chart_roundtrips(song: Song, circle_free: bool) -> None:
    dump_and_load_then_compare(
        Format.MONO_COLUMN,
        song,
        bytes_decoder=lambda b: b.decode("shift-jis-2004", errors="surrogateescape"),
        dump_options={"circle_free": circle_free},
    )
