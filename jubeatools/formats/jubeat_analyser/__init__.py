"""
Formats read by jubeat analyser

memo is a vague term refering to several legacy formats.
They were originally derived from the (somewhat) human-readable format choosen
by websites storing official jubeat charts in text form as a memory aid.

The machine-readable variants are partially documented (in japanese)
on these pages :
- http://yosh52.web.fc2.com/jubeat/fumenformat.html
- http://yosh52.web.fc2.com/jubeat/holdmarker.html
"""

from .mono_column.dump import dump_mono_column
from .mono_column.load import load_mono_column
from .memo.dump import dump_memo
from .memo.load import load_memo
