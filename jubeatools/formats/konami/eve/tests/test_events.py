from hypothesis import given
from hypothesis import strategies as st

from jubeatools import song
from jubeatools.formats.konami.commons import EveLong
from jubeatools.formats.timemap import TimeMap
from jubeatools.testutils import strategies as jbst


@given(
    jbst.long_note(),
    jbst.timing_info(
        with_bpm_changes=True,
        bpm_strat=st.decimals(min_value=1, max_value=1000, places=2),
        beat_zero_offset_strat=st.decimals(min_value=0, max_value=20, places=2),
    ),
)
def test_that_long_note_roundtrips(
    long_note: song.LongNote, timing: song.Timing
) -> None:
    time_map = TimeMap.from_timing(timing)
    original = EveLong.from_jubeatools(long_note, time_map)
    recovered = EveLong.from_value(original.value)
    assert recovered == original
