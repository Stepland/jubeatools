from decimal import Decimal

from hypothesis import given
import hypothesis.strategies as st

from jubeatools.song import BeatsTime, LongNote, NotePosition, TapNote, Chart, Timing, BPMEvent, SecondsTime, BeatsTime, Metadata

from ..mono_column.load import MonoColumnParser
from ..mono_column.dump import _dump_mono_column_chart

@st.composite
def beat_time(draw):
    numerator = draw(st.integers(min_value=0, max_value=240*4*10))
    return BeatsTime(numerator, 240)

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
        events=[BPMEvent(BeatsTime(0), Decimal(120))],
        beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(
        level=0,
        timing=timing,
        notes=sorted(notes, key=lambda n: (n.time, n.position))
    )
    metadata = Metadata("", "", "", "")
    string_io = _dump_mono_column_chart("", chart, metadata, timing)
    chart = string_io.getvalue()
    parser = MonoColumnParser()
    for line in chart.split("\n"):
        parser.load_line(line)
    actual = set(parser.notes())
    assert notes == actual
