from pathlib import Path
from typing import Any, Callable, Dict

import simplejson as json

from jubeatools import song as jbt
from jubeatools.formats.dump_tools import FileNameFormat
from jubeatools.formats.load_tools import FolderLoader, make_folder_loader
from jubeatools.formats.typing import Dumper, Loader, SongFileDumper


def _load_raw_memon(path: Path) -> Any:
    with path.open() as f:
        return json.load(f, use_decimal=True)


load_folder: FolderLoader[Any] = make_folder_loader("*.memon", _load_raw_memon)


def make_memon_folder_loader(memon_loader: Callable[[Any], jbt.Song]) -> Loader:
    """Create memon folder loader from the given file loader"""

    def load(path: Path, merge: bool = False, **kwargs: Any) -> jbt.Song:
        files = load_folder(path)
        if not merge and len(files) > 1:
            raise ValueError(
                "Multiple .memon files were found in the given folder, "
                "use the --merge option if you want to make a single memon file "
                "out of several that each containt a different chart (or set of "
                "charts) for the same song"
            )

        charts = [memon_loader(d) for d in files.values()]
        return jbt.Song.from_monochart_instances(*charts)

    return load


def make_memon_dumper(internal_dumper: SongFileDumper) -> Dumper:
    def dump(song: jbt.Song, path: Path, **kwargs: dict) -> Dict[Path, bytes]:
        name_format = FileNameFormat(Path("{title}.memon"), suggestion=path)
        songfile = internal_dumper(song, **kwargs)
        filepath = name_format.available_filename_for(songfile)
        return {filepath: songfile.contents}

    return dump
