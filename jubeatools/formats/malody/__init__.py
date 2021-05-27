"""Malody is a multiplatform rhythm game that mainly lives off content created
by its community, as is common in the rhythm game simulator scene. It support
many different games or "Modes", including jubeat (known as "Pad" Mode)

The file format it uses is not that well documented but is simple enough to
make sense of without docs. It's a json file with some defined schema"""

from .dump import dump_malody
from .load import load_malody
