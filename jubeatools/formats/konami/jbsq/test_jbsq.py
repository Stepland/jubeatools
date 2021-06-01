from hypothesis import given

from jubeatools import song
from jubeatools.formats import Format
from jubeatools.formats.konami.testutils import eve_compatible_song
from jubeatools.testutils.test_patterns import dump_and_load_then_compare

from .construct import jbsq


@given(eve_compatible_song())
def test_that_full_chart_roundtrips(song: song.Song) -> None:
    dump_and_load_then_compare(
        Format.JBSQ,
        song,
        bytes_decoder=lambda b: str(jbsq.parse(b)),
        load_options={"beat_snap": 12},
    )
