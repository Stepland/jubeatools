"""
This module contains code for the different formats read by jubeat analyser

"memo" is a vague term that refers to several legacy formats.
They were originally derived from the (somewhat) human-readable format choosen
by websites gathering official jubeat charts in text form as a memory aid.

The machine-readable variants are partially documented (in japanese)
on these pages :
- http://yosh52.web.fc2.com/jubeat/fumenformat.html
- http://yosh52.web.fc2.com/jubeat/holdmarker.html
"""

from .memo1.dump import dump_memo1
from .memo1.load import load_memo1
from .memo2.dump import dump_memo2
from .memo2.load import load_memo2
from .memo.dump import dump_memo
from .memo.load import load_memo
from .mono_column.dump import dump_mono_column
from .mono_column.load import load_mono_column
