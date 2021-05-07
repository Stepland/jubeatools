from jubeatools.song import Difficulty
from typing import Dict


DIFFICULTY_NUMBER: Dict[str, int] = {
    Difficulty.BASIC: 1,
    Difficulty.ADVANCED: 2,
    Difficulty.EXTREME: 3,
}

DIFFICULTY_INDEX: Dict[str, int] = {
    Difficulty.BASIC: 0,
    Difficulty.ADVANCED: 1,
    Difficulty.EXTREME: 2,
}
