"""
This module contains code for the different formats read by "jubeat analyser".

"jubeat analyser" is a Windows program that can play back chart files and
export them to video files, it can also be used as a jubeat simulator.

"memo" is a vague term that refers to several slightly different formats.
My understanding is that they were all originally derived from the (somewhat)
human-readable format choosen by websites like jubeat memo or cosmos memo.
These websites would provide text transcripts of official jubeat charts as
training material for hardcore players.

The machine-readable variants or these text formats are partially documented
(in japanese) on these pages :
- http://yosh52.web.fc2.com/jubeat/fumenformat.html
- http://yosh52.web.fc2.com/jubeat/holdmarker.html
"""

from .memo import dump_memo, load_memo
from .memo1 import dump_memo1, load_memo1
from .memo2 import dump_memo2, load_memo2
from .mono_column import dump_mono_column, load_mono_column
