from decimal import Decimal
from pathlib import Path
from typing import List, Union

from hypothesis import example, given
from hypothesis import strategies as st

from jubeatools.formats import Format
from jubeatools.formats.jubeat_analyser.memo2.dump import _dump_memo2_chart
from jubeatools.formats.jubeat_analyser.memo2.load import Memo2Parser
from jubeatools.song import (
    BeatsTime,
    BPMEvent,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    SecondsTime,
    Song,
    TapNote,
    Timing,
)
from jubeatools.testutils.strategies import NoteOption
from jubeatools.testutils.strategies import notes as notes_strat

from ..test_utils import load_and_dump_then_check, memo_compatible_song
from . import example1, example2, example3


@given(notes_strat(NoteOption.LONGS))
def test_that_notes_roundtrip(notes: List[Union[TapNote, LongNote]]) -> None:
    timing = Timing(
        events=[BPMEvent(BeatsTime(0), Decimal(120))], beat_zero_offset=SecondsTime(0)
    )
    chart = Chart(
        level=Decimal(0),
        timing=timing,
        notes=sorted(notes, key=lambda n: (n.time, n.position)),
    )
    metadata = Metadata("", "", Path(""), Path(""))
    string_io = _dump_memo2_chart("", chart, metadata, timing)
    chart_text = string_io.getvalue()
    parser = Memo2Parser()
    for line in chart_text.split("\n"):
        parser.load_line(line)
    parser.finish_last_few_notes()
    actual = set(parser.notes())
    assert notes == actual


@given(memo_compatible_song(), st.booleans())
@example(*example1.data)
@example(*example2.data)
@example(*example3.data)
def test_that_full_chart_roundtrips(song: Song, circle_free: bool) -> None:
    load_and_dump_then_check(Format.MEMO_2, song, circle_free)
