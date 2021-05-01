from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Set, Union

from hypothesis import given, example

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
from jubeatools.formats.jubeat_analyser.memo.dump import _dump_memo_chart
from jubeatools.formats.jubeat_analyser.memo.load import MemoParser

from . import example1


@given(notes_strat(NoteOption.LONGS))
@example(example1.notes)
def test_many_notes(notes: Set[Union[TapNote, LongNote]]) -> None:
    timing = Timing(
        events=[BPMEvent(BeatsTime(0), Decimal(120))], beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(
        level=Decimal(0),
        timing=timing,
        notes=sorted(notes, key=lambda n: (n.time, n.position)),
    )
    metadata = Metadata("", "", Path(""), Path(""))
    string_io = _dump_memo_chart("", chart, metadata, timing, False)
    chart_text = string_io.getvalue()
    parser = MemoParser()
    for line in chart_text.split("\n"):
        parser.load_line(line)
    parser.finish_last_few_notes()
    actual = set(parser.notes())
    assert notes == actual
