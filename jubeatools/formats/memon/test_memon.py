import tempfile
from pathlib import Path
from typing import Set

import hypothesis.strategies as st
from hypothesis import given

from jubeatools import song
from jubeatools.formats.typing import Dumper, Loader
from jubeatools.testutils import strategies as jbst

from . import (
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    dump_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
    load_memon_legacy,
)


def dump_and_load(
    expected_song: song.Song, dump_function: Dumper, load_function: Loader
) -> None:
    with tempfile.NamedTemporaryFile(mode="wb") as file:
        files = dump_function(expected_song, Path(file.name))
        assert len(files) == 1
        filename, contents = list(files.items())[0]
        file.write(contents)
        file.seek(0)
        actual_song = load_function(Path(file.name))

    assert actual_song == expected_song


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
        )
    )
    random_song.metadata.preview = None
    random_song.metadata.preview_file = None
    return random_song


@given(memon_legacy_compatible_song())
def test_memon_legacy(song: song.Song) -> None:
    dump_and_load(song, dump_memon_legacy, load_memon_legacy)


memon_0_1_0_compatible_song = memon_legacy_compatible_song


@given(memon_0_1_0_compatible_song())
def test_memon_0_1_0(song: song.Song) -> None:
    dump_and_load(song, dump_memon_0_1_0, load_memon_0_1_0)


@st.composite
def memon_0_2_0_compatible_song(draw: st.DrawFn) -> song.Song:
    """Memon v0.2.0 does not support preview_file"""
    random_song: song.Song = draw(
        jbst.song(
            diffs_strat=memon_diffs(),
            chart_strat=jbst.chart(timing_strat=st.none()),
            common_timing_strat=jbst.timing_info(with_bpm_changes=False),
        )
    )
    random_song.metadata.preview_file = None
    return random_song


@given(memon_0_2_0_compatible_song())
def test_memon_0_2_0(song: song.Song) -> None:
    dump_and_load(song, dump_memon_0_2_0, load_memon_0_2_0)
