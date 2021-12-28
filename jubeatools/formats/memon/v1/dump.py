from collections import Counter
from functools import singledispatch
from typing import Any, Iterable, List, Optional, Set, Tuple, TypeVar, Union

import simplejson as json

from jubeatools import song as jbt
from jubeatools.formats.filetypes import SongFile
from jubeatools.utils import none_or

from ..tools import make_memon_dumper
from . import schema as memon


def _dump_memon_1_0_0(song: jbt.Song, **kwargs: Any) -> SongFile:
    metadata = dump_metadata(song.metadata)
    common_timing = dump_file_timing(song)
    charts = {
        diff: dump_chart(chart, common_timing) for diff, chart in song.charts.items()
    }
    file = memon.File(
        version="1.0.0",
        metadata=metadata,
        timing=common_timing,
        data=charts,
    )
    json_file = memon.FILE_SCHEMA.dump(file)
    file_bytes = json.dumps(json_file, indent=4, use_decimal=True).encode("utf-8")
    return SongFile(contents=file_bytes, song=song)


dump_memon_1_0_0 = make_memon_dumper(_dump_memon_1_0_0)


def dump_metadata(metadata: jbt.Metadata) -> memon.Metadata:
    return memon.Metadata(
        title=metadata.title,
        artist=metadata.artist,
        audio=none_or(str, metadata.audio),
        jacket=none_or(str, metadata.cover),
        preview=(
            none_or(str, metadata.preview_file)
            or none_or(dump_preview, metadata.preview)
        ),
    )


def dump_preview(preview: jbt.Preview) -> memon.PreviewSample:
    return memon.PreviewSample(
        start=preview.start,
        duration=preview.length,
    )


def dump_file_timing(song: jbt.Song) -> Optional[memon.Timing]:
    events = get_common_value(
        t.events for _, _, t in song.iter_charts_with_applicable_timing()
    )
    beat_zero_offset = get_common_value(
        t.beat_zero_offset for _, _, t in song.iter_charts_with_applicable_timing()
    )
    hakus = get_common_value(
        none_or(frozenset.__call__, c.hakus or song.common_hakus)
        for c in song.charts.values()
    )
    timing = dump_timing(
        events=events,
        beat_zero_offset=beat_zero_offset,
        hakus=hakus,
    )
    timing.remove_default_values()
    return timing or None


T = TypeVar("T")


def get_common_value(values: Iterable[T]) -> Optional[T]:
    possible_values = Counter(values)
    value, count = possible_values.most_common(1).pop()
    if count >= 2:
        return value
    else:
        return None


def dump_timing(
    events: Optional[Iterable[jbt.BPMEvent]],
    beat_zero_offset: Optional[jbt.SecondsTime],
    hakus: Optional[Set[jbt.BeatsTime]],
) -> memon.Timing:
    return memon.Timing(
        offset=beat_zero_offset,
        resolution=None,
        bpms=none_or(dump_bpms, events),
        hakus=none_or(dump_hakus, hakus),
    )


def dump_bpms(bpms: Iterable[jbt.BPMEvent]) -> List[memon.BPMEvent]:
    return [dump_bpm(b) for b in bpms]


def dump_bpm(bpm: jbt.BPMEvent) -> memon.BPMEvent:
    return memon.BPMEvent(beat=beats_to_best_form(bpm.time), bpm=bpm.BPM)


def beats_to_best_form(b: jbt.BeatsTime) -> memon.SymbolicTime:
    if is_expressible_as_240th(b):
        return (240 * b.numerator) // b.denominator
    else:
        return beat_to_fraction_tuple(b)


def is_expressible_as_240th(b: jbt.BeatsTime) -> bool:
    return (240 * b.numerator) % b.denominator == 0


def beat_to_fraction_tuple(b: jbt.BeatsTime) -> Tuple[int, int, int]:
    integer_part = int(b)
    remainder = b % 1
    return (
        integer_part,
        remainder.numerator,
        remainder.denominator,
    )


def dump_hakus(hakus: Set[jbt.BeatsTime]) -> List[memon.SymbolicTime]:
    return [beats_to_best_form(b) for b in sorted(hakus)]


def dump_chart(chart: jbt.Chart, file_timing: Optional[memon.Timing]) -> memon.Chart:
    return memon.Chart(
        level=chart.level,
        resolution=None,
        timing=dump_chart_timing(chart.timing, chart.hakus, file_timing),
        notes=[dump_note(n) for n in chart.notes],
    )


def dump_chart_timing(
    chart_timing: Optional[jbt.Timing],
    chart_hakus: Optional[Set[jbt.BeatsTime]],
    file_timing: Optional[memon.Timing],
) -> Optional[memon.Timing]:
    if chart_timing is None:
        events = None
        beat_zero_offset = None
    else:
        events = chart_timing.events
        beat_zero_offset = chart_timing.beat_zero_offset

    res = dump_timing(events, beat_zero_offset, chart_hakus)
    fallback = memon.Timing.fill_in_defaults(file_timing)
    return res.remove_common_values(fallback)


@singledispatch
def dump_note(n: Union[jbt.TapNote, jbt.LongNote]) -> memon.Note:
    ...


@dump_note.register
def dump_tap_note(tap: jbt.TapNote) -> memon.TapNote:
    return memon.TapNote(n=tap.position.index, t=beats_to_best_form(tap.time))


@dump_note.register
def dump_long_note(long: jbt.LongNote) -> memon.LongNote:
    return memon.LongNote(
        n=long.position.index,
        t=beats_to_best_form(long.time),
        l=beats_to_best_form(long.duration),
        p=tail_as_6_notation(long),
    )


def tail_as_6_notation(long: jbt.LongNote) -> int:
    if long.tail_tip.y == long.position.y:
        return long.tail_tip.x - int(long.tail_tip.x > long.position.x)
    else:
        return 3 + long.tail_tip.y - int(long.tail_tip.y > long.position.y)
