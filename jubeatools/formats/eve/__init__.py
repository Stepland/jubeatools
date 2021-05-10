""".eve is the file format used in arcade releases of jubeat

.eve files are CSVs with three columns : time, command, value

A small but annoying amount of precision is lost when using this format :
- time is stored already "rendered" as a whole number of ticks on a 300Hz clock
  instead of using symbolic time
- while some symbolic time information remains in the form of TEMPO, MEASURE
  and HAKU commands (respectively a BPM change, a measure marker and a beat
  marker), BPMs are stored as `int((6*10^7)/BPM)` which makes it hard to
  recover many significant digits
"""

from .dump import dump_eve
from .load import load_eve
