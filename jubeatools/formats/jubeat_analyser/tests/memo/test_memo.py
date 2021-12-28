from decimal import Decimal
from pathlib import Path
from typing import Set, Union

from hypothesis import example, given
from hypothesis import note as hypothesis_note
from hypothesis import strategies as st

from jubeatools import song
from jubeatools.formats.format_names import Format
from jubeatools.formats.jubeat_analyser.memo.dump import _dump_memo_chart
from jubeatools.formats.jubeat_analyser.memo.load import MemoParser
from jubeatools.testutils import strategies as jbst
from jubeatools.testutils.test_patterns import dump_and_load_then_compare

from ..test_utils import memo_compatible_song
from . import example1, example2, example3


@given(jbst.notes())
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
    dump_and_load_then_compare(
        Format.MEMO,
        song,
        bytes_decoder=lambda b: b.decode("shift-jis-2004", errors="surrogateescape"),
        dump_options={"circle_free": circle_free},
    )
