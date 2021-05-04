from decimal import Decimal
from pathlib import Path
from typing import List, Union

from hypothesis import example, given
from hypothesis import strategies as st

from jubeatools import song
from jubeatools.formats import Format
from jubeatools.formats.jubeat_analyser.memo1.dump import _dump_memo1_chart
from jubeatools.formats.jubeat_analyser.memo1.load import Memo1Parser
from jubeatools.testutils.strategies import NoteOption
from jubeatools.testutils.strategies import notes as notes_strat

from ..test_utils import load_and_dump_then_check, memo_compatible_song
from . import example1


@given(notes_strat(NoteOption.LONGS))
def test_that_notes_roundtrip(notes: List[Union[song.TapNote, song.LongNote]]) -> None:
    timing = song.Timing(
        events=[song.BPMEvent(song.BeatsTime(0), Decimal(120))],
        beat_zero_offset=song.SecondsTime(0),
    )
    chart = song.Chart(
        level=Decimal(0),
        timing=timing,
        notes=sorted(notes, key=lambda n: (n.time, n.position)),
    )
    metadata = song.Metadata("", "", Path(""), Path(""))
    string_io = _dump_memo1_chart("", chart, metadata, timing)
    chart_text = string_io.getvalue()
    parser = Memo1Parser()
    for line in chart_text.split("\n"):
        parser.load_line(line)
    parser.finish_last_few_notes()
    actual = set(parser.notes())
    assert notes == actual


@given(memo_compatible_song(), st.booleans())
@example(*example1.data)
def test_that_full_chart_roundtrips(song: song.Song, circle_free: bool) -> None:
    load_and_dump_then_check(Format.MEMO_1, song, circle_free)
