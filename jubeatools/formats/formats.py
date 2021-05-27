from typing import Dict

from .enum import Format
from .jubeat_analyser import (
    dump_memo,
    dump_memo1,
    dump_memo2,
    dump_mono_column,
    load_memo,
    load_memo1,
    load_memo2,
    load_mono_column,
)
from .konami import dump_eve, dump_jbsq, load_eve, load_jbsq
from .malody import dump_malody, load_malody
from .memon import (
    dump_memon_0_1_0,
    dump_memon_0_2_0,
    dump_memon_legacy,
    load_memon_0_1_0,
    load_memon_0_2_0,
    load_memon_legacy,
)
from .typing import Dumper, Loader

LOADERS: Dict[Format, Loader] = {
    Format.EVE: load_eve,
    Format.JBSQ: load_jbsq,
    Format.MALODY: load_malody,
    Format.MEMON_LEGACY: load_memon_legacy,
    Format.MEMON_0_1_0: load_memon_0_1_0,
    Format.MEMON_0_2_0: load_memon_0_2_0,
    Format.MONO_COLUMN: load_mono_column,
    Format.MEMO: load_memo,
    Format.MEMO_1: load_memo1,
    Format.MEMO_2: load_memo2,
}

DUMPERS: Dict[Format, Dumper] = {
    Format.EVE: dump_eve,
    Format.JBSQ: dump_jbsq,
    Format.MALODY: dump_malody,
    Format.MEMON_LEGACY: dump_memon_legacy,
    Format.MEMON_0_1_0: dump_memon_0_1_0,
    Format.MEMON_0_2_0: dump_memon_0_2_0,
    Format.MONO_COLUMN: dump_mono_column,
    Format.MEMO: dump_memo,
    Format.MEMO_1: dump_memo1,
    Format.MEMO_2: dump_memo2,
}
