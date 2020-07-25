from decimal import Decimal
from fractions import Fraction

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
from jubeatools.testutils.strategies import NoteOption
from jubeatools.testutils.strategies import notes as notes_strat

from ..memo.dump import _dump_memo_chart
from ..memo.load import MemoParser


@given(notes_strat(NoteOption.LONGS))
def test_many_notes(notes):
    timing = Timing(
        events=[BPMEvent(BeatsTime(0), Decimal(120))], beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(
        level=0, timing=timing, notes=sorted(notes, key=lambda n: (n.time, n.position))
    )
    metadata = Metadata("", "", "", "")
    string_io = _dump_memo_chart("", chart, metadata, timing, False)
    chart = string_io.getvalue()
    parser = MemoParser()
    for line in chart.split("\n"):
        parser.load_line(line)
    parser.finish_last_few_notes()
    actual = set(parser.notes())
    assert notes == actual
