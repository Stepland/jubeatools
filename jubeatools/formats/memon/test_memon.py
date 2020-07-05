import tempfile

import hypothesis.strategies as st
from hypothesis import given
from path import Path

from jubeatools.testutils.strategies import NoteOption, TimingOption
from jubeatools.testutils.strategies import song as song_strat

from . import (
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    dump_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
    load_memon_legacy,
)


def dump_and_load(expected_song, dump_function, load_function):
    files = dump_function(expected_song)
    assert len(files) == 1
    filename, str_io = list(files.items())[0]
    with tempfile.NamedTemporaryFile(mode="w+") as file:
        file.write(str_io.getvalue())
        file.seek(0)
        actual_song = load_function(file.name)

    assert expected_song == actual_song


@st.composite
def memon_legacy_compatible_song(draw):
    """Memon versions below v0.2.0 do not support preview metadata"""
    song = draw(song_strat(TimingOption.GLOBAL, True, NoteOption.LONGS))
    song.metadata.preview = None
    return song


@given(memon_legacy_compatible_song())
def test_memon_legacy(song):
    dump_and_load(song, dump_memon_legacy, load_memon_legacy)


memon_0_1_0_compatible_song = memon_legacy_compatible_song


@given(memon_0_1_0_compatible_song())
def test_memon_0_1_0(song):
    dump_and_load(song, dump_memon_0_1_0, load_memon_0_1_0)


@st.composite
def memon_0_2_0_compatible_song(draw):
    return draw(song_strat(TimingOption.GLOBAL, True, NoteOption.LONGS))


@given(memon_0_2_0_compatible_song())
def test_memon_0_2_0(song):
    dump_and_load(song, dump_memon_0_2_0, load_memon_0_2_0)
