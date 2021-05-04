from decimal import Decimal
from pathlib import Path
from typing import Set, Union

from hypothesis import example, given
from hypothesis import note as hypothesis_note
from hypothesis import strategies as st

from jubeatools import song
from jubeatools.formats.enum import Format
from jubeatools.formats.jubeat_analyser.memo.dump import _dump_memo_chart
from jubeatools.formats.jubeat_analyser.memo.load import MemoParser
from jubeatools.testutils import strategies as jbst

from ..test_utils import load_and_dump_then_check, memo_compatible_song
from . import example1, example2, example3


@given(jbst.notes(jbst.NoteOption.LONGS))
@example(example1.notes)
def test_that_notes_roundtrip(notes: Set[Union[song.TapNote, song.LongNote]]) -> None:
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
    string_io = _dump_memo_chart("", chart, metadata, timing, False)
    chart_text = string_io.getvalue()
    hypothesis_note(f"Chart :\n{chart_text}")
    parser = MemoParser()
    for line in chart_text.split("\n"):
        parser.load_line(line)
    parser.finish_last_few_notes()
    actual = set(parser.notes())
    assert notes == actual


@given(memo_compatible_song(), st.booleans())
@example(*example2.data)
@example(*example3.data)
def test_that_full_chart_roundtrips(song: song.Song, circle_free: bool) -> None:
    load_and_dump_then_check(Format.MEMO, song, circle_free)
