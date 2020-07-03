from decimal import Decimal

import hypothesis.strategies as st
from hypothesis import given

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

from ..mono_column.dump import _dump_mono_column_chart
from ..mono_column.load import MonoColumnParser


@st.composite
def beat_time(draw):
    denominator = draw(st.sampled_from([4, 8, 16, 3, 5]))
    numerator = draw(st.integers(min_value=0, max_value=denominator * 4 * 10))
    return BeatsTime(numerator, denominator)


@st.composite
def note_position(draw):
    x = draw(st.integers(min_value=0, max_value=3))
    y = draw(st.integers(min_value=0, max_value=3))
    return NotePosition(x, y)


@st.composite
def tap_note(draw):
    time = draw(beat_time())
    position = draw(note_position())
    return TapNote(time, position)


@given(st.sets(tap_note(), min_size=1, max_size=2000))
def test_tap_notes(notes):
    timing = Timing(
        events=[BPMEvent(BeatsTime(0), Decimal(120))], beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(
        level=0, timing=timing, notes=sorted(notes, key=lambda n: (n.time, n.position))
    )
    metadata = Metadata("", "", "", "")
    string_io = _dump_mono_column_chart("", chart, metadata, timing)
    chart = string_io.getvalue()
    parser = MonoColumnParser()
    for line in chart.split("\n"):
        parser.load_line(line)
    actual = set(parser.notes())
    assert notes == actual


@st.composite
def long_note(draw):
    time = draw(beat_time())
    duration = draw(st.integers(min_value=1, max_value=time.denominator * 4 * 3))
    position = draw(note_position())
    tail_index = draw(st.integers(min_value=0, max_value=5))
    if tail_index >= 3:
        y = sorted(set(range(4)).difference([position.y]))[tail_index - 3]
        tail_tip = NotePosition(position.x, y)
    else:
        x = sorted(set(range(4)).difference([position.x]))[tail_index]
        tail_tip = NotePosition(x, position.y)
    return LongNote(time, position, BeatsTime(duration, time.denominator), tail_tip)


@given(long_note())
def test_single_long_note(note):
    timing = Timing(
        events=[BPMEvent(BeatsTime(0), Decimal(120))], beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(level=0, timing=timing, notes=[note])
    metadata = Metadata("", "", "", "")
    string_io = _dump_mono_column_chart("", chart, metadata, timing)
    chart = string_io.getvalue()
    parser = MonoColumnParser()
    for line in chart.split("\n"):
        parser.load_line(line)
    actual = set(parser.notes())
    assert set([note]) == actual
