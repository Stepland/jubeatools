"""
Mono column (not an official name)

It's the format jubeat analyser expects when otherwise no format command has
been found (like #memo #memo1 #memo2 or #boogie)

Mono-column files are usually properly decoded using `shift-jis-2004`

Mono-column files are made up of several sections.
Each section is made up of a series of command lines and chart lines.
The section end is marked by a line starting with "--"

Command lines follow the usual jubeat analyser command pattern

Chart lines come in groups of 4 in each section.
A group of 4 chart lines makes up a frame, which contains the note symbols.

Note symbols encode both the position and the time. The position is determined
"visually" by the position the note symbol occupies in the frame.
The time within the frame is determined by the precise symbol used.

The default note symbols are the circled numbers from ① to ⑯, they represent
"""

from .dump import dump_mono_column
from .load import load_mono_column
