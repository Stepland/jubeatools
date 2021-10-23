from decimal import Decimal

from hypothesis import strategies as st

from jubeatools import song
from jubeatools.testutils import strategies as jbst

simple_beat_strat = jbst.beat_time(
    denominator_strat=st.sampled_from([4, 3]), max_section=10
)


@st.composite
def eve_compatible_song(draw: st.DrawFn) -> song.Song:
    """eve only keeps notes, timing info and difficulty,
    the precision you can get out of it is also severly limited"""
    diff = draw(st.sampled_from(list(song.Difficulty)))
    chart = draw(
        jbst.chart(
            timing_strat=jbst.timing_info(
                with_bpm_changes=True,
                bpm_strat=st.decimals(min_value=50, max_value=300, places=2),
                beat_zero_offset_strat=st.decimals(min_value=0, max_value=20, places=2),
                time_strat=jbst.beat_time(
                    min_section=1,
                    max_section=10,
                    denominator_strat=st.sampled_from([4, 3]),
                ),
            ),
            notes_strat=jbst.notes(
                note_strat=st.one_of(
                    jbst.tap_note(time_strat=simple_beat_strat),
                    jbst.long_note(
                        time_strat=simple_beat_strat,
                        duration_strat=jbst.beat_time(
                            min_numerator=1,
                            max_section=3,
                            denominator_strat=st.sampled_from([4, 3]),
                        ),
                    ),
                ),
                beat_time_strat=simple_beat_strat,
            ),
            level_strat=st.just(Decimal(0)),
        )
    )
    return song.Song(
        metadata=song.Metadata(),
        charts={diff: chart},
    )
