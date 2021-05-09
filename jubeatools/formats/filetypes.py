from dataclasses import dataclass

from jubeatools.song import Chart, Song


@dataclass
class JubeatFile:
    contents: bytes


@dataclass
class SongFile(JubeatFile):
    """File representing a collection of charts with metadata,
    like a .memon file for example"""

    song: Song


@dataclass
class ChartFile(SongFile):
    """File representing a single chart (with possibly some metadata),
    Used in jubeat analyser formats for instance"""

    difficulty: str
    chart: Chart
