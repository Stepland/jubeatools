import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from hypothesis import strategies as st

from jubeatools import song
from jubeatools.testutils import strategies as jbst
from jubeatools.testutils.typing import DrawFunc


@st.composite
def memo_compatible_metadata(draw: DrawFunc) -> song.Metadata:
    text_strat = st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E))
    metadata: song.Metadata = draw(
        jbst.metadata(text_strat=text_strat, path_strat=text_strat)
    )
    metadata.preview = None
    metadata.preview_file = None
    return metadata


@st.composite
def memo_compatible_song(draw: DrawFunc) -> song.Song:
    """Memo only supports one difficulty per file"""
    diff = draw(st.sampled_from(list(d.value for d in song.Difficulty)))
    chart = draw(
        jbst.chart(
            timing_strat=jbst.timing_info(with_bpm_changes=True),
            notes_strat=jbst.notes(),
        )
    )
    metadata: song.Metadata = draw(memo_compatible_metadata())
    return song.Song(
        metadata=metadata,
        charts={diff: chart},
    )


@contextmanager
def temp_file_named_txt() -> Iterator[Path]:
    with tempfile.NamedTemporaryFile(suffix=".txt") as dst:
        yield Path(dst.name)
