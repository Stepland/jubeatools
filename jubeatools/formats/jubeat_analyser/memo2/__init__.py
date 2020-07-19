"""
memo2

memo2 is the jubeat analyser version of youbeat files :

http://yosh52.web.fc2.com/jubeat/fumenformat.html

A chart in this format needs to have a `#memo2` line somewhere to indicate its format
"""

from .dump import dump_memo2
from .load import load_memo2
