from pathlib import Path
from typing import Dict, List, TypeVar, Protocol, Generic, Optional


T = TypeVar("T")

class FileLoader(Protocol, Generic[T]):
    """Function that excepts a path to a file as a parameter and returns its
    contents in whatever form suitable for the current format. Returns None in
    case of error"""
    def __call__(self, path: Path) -> Optional[T]:
        ...

class FolderLoader(Protocol, Generic[T]):
    """Function that expects a folder or a file path as a parameter. Loads
    either all valid files in the folder or just the given file depending on
    the argument"""
    def __call__(self, path: Path) -> Dict[Path, T]:
        ...

def make_folder_loader(
    glob_pattern: str,
    file_loader: FileLoader
) -> FolderLoader:

    def folder_loader(path: Path) -> Dict[Path, T]:
        files: Dict[Path, T] = {}
        if path.is_dir():
            paths = path.glob(glob_pattern)
        else:
            paths = [path]
        
        for p in paths:
            value = file_loader(p)
            if value is not None:
                files[p] = value

        return files
    
    return folder_loader
