import tempfile
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import given

from jubeatools.formats.typing import Dumper, Loader
from jubeatools.song import Song
from jubeatools.testutils.strategies import NoteOption, TimingOption
from jubeatools.testutils.strategies import song as song_strat
from jubeatools.testutils.typing import DrawFunc

from . import (
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    dump_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
    load_memon_legacy,
)


def dump_and_load(
    expected_song: Song, dump_function: Dumper, load_function: Loader
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
def memon_legacy_compatible_song(draw: DrawFunc) -> Song:
    """Memon versions below v0.2.0 do not support any preview metadata"""
    song: Song = draw(song_strat(TimingOption.GLOBAL, True, NoteOption.LONGS))
    song.metadata.preview = None
    song.metadata.preview_file = None
    return song


@given(memon_legacy_compatible_song())
def test_memon_legacy(song: Song) -> None:
    dump_and_load(song, dump_memon_legacy, load_memon_legacy)


memon_0_1_0_compatible_song = memon_legacy_compatible_song


@given(memon_0_1_0_compatible_song())
def test_memon_0_1_0(song: Song) -> None:
    dump_and_load(song, dump_memon_0_1_0, load_memon_0_1_0)


@st.composite
def memon_0_2_0_compatible_song(draw: DrawFunc) -> Song:
    """Memon v0.2.0 does not support preview_file"""
    song: Song = draw(song_strat(TimingOption.GLOBAL, True, NoteOption.LONGS))
    song.metadata.preview_file = None
    return song


@given(memon_0_2_0_compatible_song())
def test_memon_0_2_0(song: Song) -> None:
    dump_and_load(song, dump_memon_0_2_0, load_memon_0_2_0)
