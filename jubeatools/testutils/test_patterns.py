import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, ContextManager, Iterator, Optional

from hypothesis import note

from jubeatools import song
from jubeatools.formats import DUMPERS, LOADERS
from jubeatools.formats.enum import Format
from jubeatools.formats.guess import guess_format


@contextmanager
def open_temp_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def dump_and_load_then_compare(
    format_: Format,
    song: song.Song,
    bytes_decoder: Callable[[bytes], str],
    temp_path: Callable[[], ContextManager[Path]] = open_temp_dir,
    load_options: Optional[dict] = None,
    dump_options: Optional[dict] = None,
) -> None:
    load_options = load_options or {}
    dump_options = dump_options or {}
    loader = LOADERS[format_]
    dumper = DUMPERS[format_]
    with temp_path() as folder_path:
        files = dumper(song, folder_path, **dump_options)
        for file_path, bytes_ in files.items():
            file_path.write_bytes(bytes_)
            note(f"Wrote to {file_path} :\n{bytes_decoder(bytes_)}")
            assert guess_format(file_path) == format_
        recovered_song = loader(folder_path, **load_options)
        assert recovered_song == song
