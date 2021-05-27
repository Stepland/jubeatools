from enum import Enum


class Format(str, Enum):
    EVE = "eve"
    JBSQ = "jbsq"
    MALODY = "malody"
    MEMON_LEGACY = "memon:legacy"
    MEMON_0_1_0 = "memon:v0.1.0"
    MEMON_0_2_0 = "memon:v0.2.0"
    MONO_COLUMN = "mono-column"
    MEMO = "memo"
    MEMO_1 = "memo1"
    MEMO_2 = "memo2"
