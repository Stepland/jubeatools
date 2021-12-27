from pathlib import Path
from typing import Set

import hypothesis.strategies as st
from hypothesis import given

from jubeatools import song
from jubeatools.formats.format_names import Format
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
def memon_1_0_0_compatible_song(draw: st.DrawFn) -> song.Song:
    """Memon v1.0.0 only support one kind of metadata at once"""
    random_song: song.Song = draw(
        jbst.song(
            diffs_strat=memon_diffs(),
            common_hakus_strat=st.one_of(st.none(), jbst.hakus()),
            chart_strat=jbst.chart(
                hakus_strat=st.one_of(st.none(), jbst.hakus()),
            ),
        )
    )
    preview = draw(st.one_of(jbst.metadata_path_strat(), jbst.preview()))
    if isinstance(preview, str):
        random_song.metadata.preview = None
        random_song.metadata.preview_file = Path(preview)
    else:
        random_song.metadata.preview = preview
        random_song.metadata.preview_file = None

    return random_song


@given(memon_1_0_0_compatible_song())
def test_memon_1_0_0(song: song.Song) -> None:
    dump_and_load_then_compare(Format.MEMON_1_0_0, song)
