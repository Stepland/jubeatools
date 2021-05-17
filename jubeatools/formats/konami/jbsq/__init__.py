""".jbsq is the file format used in the iOS and Android app Jubeat plus

It's a binary version of the .eve format, with the same limitations.

I wanted to try kaitai for this but it doesn't support serializing right now"""

from .dump import dump_jbsq
from .load import load_jbsq
