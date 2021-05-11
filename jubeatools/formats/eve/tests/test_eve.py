import tempfile
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from hypothesis import Verbosity, given, settings
from hypothesis import strategies as st

from jubeatools import song
from jubeatools.formats import Format
from jubeatools.testutils import strategies as jbst
from jubeatools.testutils.test_patterns import dump_and_load_then_compare
from jubeatools.testutils.typing import DrawFunc

simple_beat_strat = jbst.beat_time(
    denominator_strat=st.sampled_from([4, 8, 3]), max_section=10
)


@st.composite
def eve_compatible_song(draw: DrawFunc) -> song.Song:
    """eve only keeps notes, timing info and difficulty"""
    diff = draw(st.sampled_from(list(song.Difficulty)))
    chart = draw(
        jbst.chart(
            timing_strat=jbst.timing_info(
                with_bpm_changes=True,
                bpm_strat=st.decimals(min_value=1, max_value=500, places=2),
                beat_zero_offset_strat=st.decimals(min_value=0, max_value=20, places=2),
                time_strat=simple_beat_strat,
            ),
            notes_strat=jbst.notes(
                note_strat=st.one_of(
                    jbst.tap_note(time_start=simple_beat_strat),
                    jbst.long_note(
                        time_strat=simple_beat_strat,
                        duration_strat=jbst.beat_time(
                            min_numerator=1,
                            max_section=3,
                            denominator_strat=st.sampled_from([4, 8, 3]),
                        ),
                    ),
                )
            ),
            level_strat=st.just(Decimal(0)),
        )
    )
    return song.Song(
        metadata=song.Metadata(),
        charts={diff: chart},
    )


@contextmanager
def open_temp_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@given(eve_compatible_song())
@settings(verbosity=Verbosity.normal)
def test_that_full_chart_roundtrips(song: song.Song) -> None:
    dump_and_load_then_compare(
        Format.EVE,
        song,
        temp_path=open_temp_dir(),
        bytes_decoder=lambda b: b.decode("ascii"),
    )
