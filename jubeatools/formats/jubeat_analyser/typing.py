from io import StringIO
from typing import Protocol

from jubeatools.song import Chart, Metadata, Timing


class JubeatAnalyserChartDumper(Protocol):
    """Internal Dumper for jubeat analyser formats"""

    def __call__(
        self,
        difficulty: str,
        chart: Chart,
        metadata: Metadata,
        timing: Timing,
        circle_free: bool = False,
    ) -> StringIO:
        ...
