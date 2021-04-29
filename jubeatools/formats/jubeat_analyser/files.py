from pathlib import Path
from typing import Dict, List


def load_files(path: Path) -> Dict[Path, List[str]]:
    # The vast majority of memo files you will encounter will be propely
    # decoded using shift-jis-2004. Get ready for endless fun with the small
    # portion of files that won't
    files: Dict[Path, List[str]] = {}
    if path.is_dir():
        for f in path.glob("*.txt"):
            _load_file(f, files)
    elif path.is_file():
        _load_file(path, files)
    return files


def _load_file(path: Path, files: Dict[Path, List[str]]) -> None:
    try:
        files[path] = path.read_text(encoding="shift-jis-2004").split("\n")
    except UnicodeDecodeError:
        pass
