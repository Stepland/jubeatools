import tempfile
from pathlib import Path

from hypothesis import note as hypothesis_note
from hypothesis import strategies as st

from jubeatools import song
from jubeatools.formats import DUMPERS, LOADERS, Format
from jubeatools.formats.guess import guess_format
from jubeatools.testutils import strategies as jbst
from jubeatools.testutils.typing import DrawFunc


@st.composite
def memo_compatible_metadata(draw: DrawFunc) -> song.Metadata:
    text_strat = st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E))
    metadata: song.Metadata = draw(
        jbst.metadata(text_strat=text_strat, path_start=text_strat)
    )
    metadata.preview = None
    metadata.preview_file = None
    return metadata


@st.composite
def memo_compatible_song(draw: DrawFunc) -> song.Song:
    """Memo only supports one difficulty per file"""
    diff = draw(st.sampled_from(["BSC", "ADV", "EXT"]))
    chart = draw(
        jbst.chart(
            timing_strat=jbst.timing_info(bpm_changes=True),
            notes_strat=jbst.notes(jbst.NoteOption.LONGS),
        )
    )
    metadata: song.Metadata = draw(memo_compatible_metadata())
    return song.Song(
        metadata=metadata,
        charts={diff: chart},
    )


def load_and_dump_then_check(f: Format, song: song.Song, circle_free: bool) -> None:
    loader = LOADERS[f]
    dumper = DUMPERS[f]
    with tempfile.NamedTemporaryFile(suffix=".txt") as dst:
        path = Path(dst.name)
        files = dumper(song, path, circle_free=circle_free)
        assert len(files) == 1
        bytes_ = files.popitem()[1]
        hypothesis_note(f"Chart file :\n{bytes_.decode('shift-jis-2004')}")
        dst.write(bytes_)
        dst.flush()
        assert guess_format(path) == f
        recovered_song = loader(path)
        assert recovered_song == song
