"""
memo

memo is the first (and probably oldest) youbeat-like format jubeat analyser
supports, the japanese docs give a good overview of what it looks like :

http://yosh52.web.fc2.com/jubeat/fumenformat.html

A chart in this format needs to have a `#memo` line somewhere to indicate its format

Like youbeat chart files, the position and timing information is split between
the left and right columns. However the timing column works differently.
In this precise format, the symbols in the timing part must only be interpeted
as quarter notes, even in the rare cases where a timing line is shorter than 4
symbols. It can never be longer than 4 either.
"""

from .dump import dump_memo
from .load import load_memo
