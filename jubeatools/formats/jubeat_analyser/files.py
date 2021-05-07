from pathlib import Path
from typing import Dict, List, Optional

from jubeatools.formats.files import make_folder_loader

def read_jubeat_analyser_file(path: Path) -> Optional[List[str]]:
    try:
        # The vast majority of memo files you will encounter will be propely
        # decoded using shift-jis-2004. Get ready for endless fun with the small
        # portion of files that won't
        lines = path.read_text(encoding="shift-jis-2004").split("\n")
    except UnicodeDecodeError:
        return None
    else:
        return lines

load_folder = make_folder_loader(
    glob_pattern="*.txt",
    file_loader=read_jubeat_analyser_file,
)
