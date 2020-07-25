from enum import Enum


class Format(str, Enum):
    MEMON_LEGACY = "memon:legacy"
    MEMON_0_1_0 = "memon:v0.1.0"
    MEMON_0_2_0 = "memon:v0.2.0"
    MONO_COLUMN = "mono-column"
    MEMO = "memo"
    MEMO_1 = "memo1"
    MEMO_2 = "memo2"


JUBEAT_ANALYSER_FORMATS = {
    Format.MONO_COLUMN,
    Format.MEMO,
    Format.MEMO_1,
    Format.MEMO_2,
}
