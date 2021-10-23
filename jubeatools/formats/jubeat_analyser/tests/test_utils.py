import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from hypothesis import strategies as st

from jubeatools import song
from jubeatools.testutils import strategies as jbst


@st.composite
def memo_compatible_metadata(draw: st.DrawFn) -> song.Metadata:
    # some ranges that are valid in shift-jis
    text_strat = st.text(
        alphabet=st.one_of(
            *(
                st.characters(min_codepoint=a, max_codepoint=b)
                for a, b in (
                    (0x20, 0x7F),
                    (0xB6, 0x109),
                    (0x410, 0x44F),
                    (0x24D0, 0x24E9),
                    (0x3041, 0x3096),
                    (0x309B, 0x30FF),
                    (0xFA30, 0xFA6A),
                    (0xFF01, 0xFF3B),
                    (0xFF3D, 0xFF5D),
                    (0xFF61, 0xFF9F),
                )
            )
        )
    )
    metadata: song.Metadata = draw(
        jbst.metadata(text_strat=text_strat, path_strat=text_strat)
    )
    metadata.preview = None
    metadata.preview_file = None
    return metadata


@st.composite
def memo_compatible_song(draw: st.DrawFn) -> song.Song:
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
