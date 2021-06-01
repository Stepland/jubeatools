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
    SecondsTime,
    Song,
    TapNote,
    Timing,
)
from jubeatools.testutils.strategies import notes as notes_strat
from jubeatools.testutils.test_patterns import dump_and_load_then_compare

from ..test_utils import memo_compatible_song
from . import example1, example2, example3


@given(notes_strat())
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
    dump_and_load_then_compare(
        Format.MEMO_2,
        song,
        bytes_decoder=lambda b: b.decode("shift-jis-2004", errors="surrogateescape"),
        dump_options={"circle_free": circle_free},
    )
