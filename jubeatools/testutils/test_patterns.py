from pathlib import Path
from typing import Callable, ContextManager, Optional

from hypothesis import note

from jubeatools import song
from jubeatools.formats import DUMPERS, LOADERS
from jubeatools.formats.enum import Format
from jubeatools.formats.guess import guess_format


def dump_and_load_then_compare(
    format_: Format,
    song: song.Song,
    temp_path: ContextManager[Path],
    bytes_decoder: Callable[[bytes], str],
    load_options: Optional[dict] = None,
    dump_options: Optional[dict] = None,
) -> None:
    load_options = load_options or {}
    dump_options = dump_options or {}
    loader = LOADERS[format_]
    dumper = DUMPERS[format_]
    with temp_path as path:
        files = dumper(song, path, **dump_options)
        for path, bytes_ in files.items():
            path.write_bytes(bytes_)
            note(f"Wrote to {path} :\n{bytes_decoder(bytes_)}")
            assert guess_format(path) == format_
        recovered_song = loader(path, **load_options)
        assert recovered_song == song
