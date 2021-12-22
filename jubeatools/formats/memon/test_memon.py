from typing import Set

import hypothesis.strategies as st
from hypothesis import given

from jubeatools import song
from jubeatools.formats.enum import Format
from jubeatools.testutils import strategies as jbst
from jubeatools.testutils.test_patterns import dump_and_load_then_compare


@st.composite
def memon_diffs(draw: st.DrawFn) -> Set[str]:
    simple_diff_names = st.sampled_from(list(d.value for d in song.Difficulty))
    diff_names = st.one_of(
        simple_diff_names,
        st.text(
            alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
            min_size=1,
            max_size=20,
        ),
    )
    s: Set[str] = draw(st.sets(diff_names, min_size=1, max_size=10))
    return s


@st.composite
def memon_legacy_compatible_song(draw: st.DrawFn) -> song.Song:
    """Memon versions below v0.2.0 do not support any preview metadata"""
    random_song: song.Song = draw(
        jbst.song(
            diffs_strat=memon_diffs(),
            chart_strat=jbst.chart(timing_strat=st.none()),
            common_timing_strat=jbst.timing_info(with_bpm_changes=False),
            metadata_strat=jbst.metadata(
                text_strat=st.text(
                    alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
                ),
            ),
        )
    )
    random_song.metadata.preview = None
    random_song.metadata.preview_file = None
    return random_song


@given(memon_legacy_compatible_song())
def test_memon_legacy(song: song.Song) -> None:
    dump_and_load_then_compare(Format.MEMON_LEGACY, song)


memon_0_1_0_compatible_song = memon_legacy_compatible_song


@given(memon_0_1_0_compatible_song())
def test_memon_0_1_0(song: song.Song) -> None:
    dump_and_load_then_compare(Format.MEMON_0_1_0, song)


@st.composite
def memon_0_2_0_compatible_song(draw: st.DrawFn) -> song.Song:
    """Memon v0.2.0 does not support preview_file"""
    random_song: song.Song = draw(
        jbst.song(
            diffs_strat=memon_diffs(),
            chart_strat=jbst.chart(timing_strat=st.none()),
            common_timing_strat=jbst.timing_info(with_bpm_changes=False),
            metadata_strat=jbst.metadata(
                text_strat=st.text(
                    alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
                ),
            ),
        )
    )
    random_song.metadata.preview_file = None
    return random_song


@given(memon_0_2_0_compatible_song())
def test_memon_0_2_0(song: song.Song) -> None:
    dump_and_load_then_compare(Format.MEMON_0_2_0, song)


@st.composite
def memon_0_3_0_compatible_song(draw: st.DrawFn) -> song.Song:
    return draw(
        jbst.song(
            diffs_strat=memon_diffs(),
            chart_strat=jbst.chart(timing_strat=st.none()),
            common_timing_strat=jbst.timing_info(with_bpm_changes=False),
            metadata_strat=jbst.metadata(
                text_strat=st.text(
                    alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
                ),
            ),
        )
    )


@given(memon_0_3_0_compatible_song())
def test_memon_0_3_0(song: song.Song) -> None:
    dump_and_load_then_compare(Format.MEMON_0_3_0, song)
