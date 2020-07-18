"""
memo1

memo1 is an hybrid between youbeat and memo :

http://yosh52.web.fc2.com/jubeat/fumenformat.html

A chart in this format needs to have a `#memo1` line somewhere to indicate its format

It's very similar to memo, except it handles irregular timing bars which make
mono-column-style symbol definitions obsolete. Unlike #memo2 or youbeat however,
it does not handle in-bar bpm changes and pauses.
"""

from .dump import dump_memo1
from .load import load_memo1
