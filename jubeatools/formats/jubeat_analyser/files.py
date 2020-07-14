from typing import Dict, List

from path import Path


def load_files(path: Path) -> Dict[Path, List[str]]:
    # The vast majority of memo files you will encounter will be propely
    # decoded using shift_jis_2004. Get ready for endless fun with the small
    # portion of files that won't
    files = {}
    if path.isdir():
        for f in path.files("*.txt"):
            _load_file(f, files)
    elif path.isfile():
        _load_file(path, files)
    return files


def _load_file(path: Path, files: Dict[Path, List[str]]):
    try:
        files[path] = path.lines("shift_jis_2004")
    except UnicodeDecodeError:
        pass
