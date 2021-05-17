from pathlib import Path
from typing import List

from jubeatools import song
from jubeatools.formats.dump_tools import make_dumper_from_chart_file_dumper
from jubeatools.formats.filetypes import ChartFile

from ..dump_tools import make_events_from_chart


def _dump_eve(song: song.Song, **kwargs: dict) -> List[ChartFile]:
    res = []
    for dif, chart, timing in song.iter_charts_with_timing():
        events = make_events_from_chart(chart.notes, timing)
        chart_text = "\n".join(e.dump() for e in events)
        chart_bytes = chart_text.encode("ascii")
        res.append(ChartFile(chart_bytes, song, dif, chart))

    return res


dump_eve = make_dumper_from_chart_file_dumper(
    internal_dumper=_dump_eve, file_name_template=Path("{difficulty:l}.eve")
)
