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
    with temp_path as folder_path:
        files = dumper(song, folder_path, **dump_options)
        for file_path, bytes_ in files.items():
            file_path.write_bytes(bytes_)
            note(f"Wrote to {file_path} :\n{bytes_decoder(bytes_)}")
            assert guess_format(file_path) == format_
        recovered_song = loader(folder_path, **load_options)
        assert recovered_song == song
