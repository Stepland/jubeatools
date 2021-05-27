from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from jubeatools import song
from jubeatools.formats import Format
from jubeatools.formats.konami.testutils import open_temp_dir
from jubeatools.testutils import strategies as jbst
from jubeatools.testutils.test_patterns import dump_and_load_then_compare
from jubeatools.testutils.typing import DrawFunc


@st.composite
def malody_compatible_song(draw: DrawFunc) -> song.Song:
    """Malody files only hold one chart and have limited metadata"""
    diff = draw(st.sampled_from(list(song.Difficulty))).value
    chart = draw(jbst.chart(level_strat=st.just(Decimal(0))))
    metadata = draw(jbst.metadata())
    metadata.preview = None
    metadata.preview_file = None
    return song.Song(metadata=metadata, charts={diff: chart})


@given(malody_compatible_song())
def test_that_full_chart_roundtrips(song: song.Song) -> None:
    dump_and_load_then_compare(
        Format.MALODY,
        song,
        temp_path=open_temp_dir(),
        bytes_decoder=lambda b: b.decode("utf-8"),
    )
