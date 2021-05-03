from decimal import Decimal
from pathlib import Path

from jubeatools.song import *

data = (
    Song(
        metadata=Metadata(
            title="",
            artist="",
            audio=Path(""),
            cover=Path(""),
            preview=None,
            preview_file=None,
        ),
        charts={
            "BSC": Chart(
                level=Decimal("0.0"),
                timing=Timing(
                    events=[
                        BPMEvent(time=Fraction(0, 1), BPM=Decimal("1.000")),
                        BPMEvent(time=Fraction(8, 1), BPM=Decimal("1.000")),
                    ],
                    beat_zero_offset=Decimal("0.000"),
                ),
                notes=[],
            )
        },
        global_timing=None,
    ),
    False,
)
