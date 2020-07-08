from jubeatools.song import Song
from path import Path
from ..parser import JubeatAnalyserParser
from dataclasses import dataclass
from typing import List



class MemoParser(JubeatAnalyserParser):
    def __init__(self):
        super().__init__()
        self.sections: List[MemoLoadedSection] = []
    
    def do_memo(self):
        ...
        
    def do_memo1(self):
        raise ValueError("This is not a memo file")

    do_boogie = do_memo2 = do_memo1

    def do_bpp(self, value):
        if self.sections:
            raise ValueError(
                "jubeatools does not handle changing the bytes per panel value halfway"
            )
        else:
            super().do_bpp(value)
    

    def append_chart_line(self, position: str):
        if self.bytes_per_panel == 1 and len(line) != 4:
            raise SyntaxError(f"Invalid chart line for #bpp=1 : {line}")
        elif self.bytes_per_panel == 2 and len(line.encode("shift_jis_2004")) != 8:
            raise SyntaxError(f"Invalid chart line for #bpp=2 : {line}")
        self.current_chart_lines.append(line)

def load_memo(path: Path) -> Song:
    # The vast majority of memo files you will encounter will be propely
    # decoded using shift_jis_2004. Get ready for endless fun with the small
    # portion of files that won't
    with open(path, encoding="shift_jis_2004") as f:
        lines = f.readlines()