from dataclasses import replace
from decimal import Decimal
from functools import partial, singledispatch
from pathlib import Path
from typing import Any, List, Set, Tuple, Union

from jubeatools import song as jbt
from jubeatools.utils import none_or

from ..tools import make_memon_folder_loader
from . import schema as memon


def _load_memon_1_0_0(raw_json: Any) -> jbt.Song:
    file: memon.File = memon.FILE_SCHEMA.load(raw_json)

    metadata = none_or(load_metadata, file.metadata) or jbt.Metadata()
    charts = {diff: load_chart(chart, file) for diff, chart in file.data.items()}
    if not file.timing:
        common_timing = None
        common_hakus = None
    else:
        timing = memon.Timing.fill_in_defaults(file.timing)
        common_timing = load_timing(timing)
        resolution = timing.resolution or 240
        load_hakus_with_res = partial(load_hakus, resolution=resolution)
        common_hakus = none_or(load_hakus_with_res, file.timing.hakus)

    return jbt.Song(
        metadata=metadata,
        charts=charts,
        common_timing=common_timing,
        common_hakus=common_hakus,
    )


load_memon_1_0_0 = make_memon_folder_loader(_load_memon_1_0_0)


def load_metadata(m: memon.Metadata) -> jbt.Metadata:
    result = jbt.Metadata(
        title=m.title,
        artist=m.artist,
        audio=none_or(Path, m.audio),
        cover=none_or(Path, m.jacket),
    )

    if m.preview is None:
        return result
    elif isinstance(m.preview, str):
        return replace(
            result,
            preview_file=Path(m.preview),
        )
    elif isinstance(m.preview, memon.PreviewSample):
        return replace(result, preview=jbt.Preview(m.preview.start, m.preview.duration))


def load_chart(c: memon.Chart, m: memon.File) -> jbt.Chart:
    applicable_timing = memon.Timing.fill_in_defaults(c.timing, m.timing)
    if not c.timing:
        timing = None
        hakus = None
    else:
        timing = load_timing(applicable_timing)
        resolution = applicable_timing.resolution or 240
        load_hakus_with_res = partial(load_hakus, resolution=resolution)
        hakus = none_or(load_hakus_with_res, c.timing.hakus)

    return jbt.Chart(
        level=c.level,
        timing=timing,
        hakus=hakus,
        notes=[load_note(n, c.resolution or 240) for n in c.notes],
    )


def load_hakus(h: List[memon.SymbolicTime], resolution: int) -> Set[jbt.BeatsTime]:
    return set(load_symbolic_time(t, resolution) for t in h)


def load_timing(t: memon.Timing) -> jbt.Timing:
    return jbt.Timing(
        events=load_bpms(t.bpms or [], t.resolution or 240),
        beat_zero_offset=t.offset or Decimal(0),
    )


def load_bpms(bpms: List[memon.BPMEvent], resolution: int) -> List[jbt.BPMEvent]:
    return [load_bpm(b, resolution) for b in bpms]


def load_bpm(bpm: memon.BPMEvent, resolution: int) -> jbt.BPMEvent:
    return jbt.BPMEvent(
        time=load_symbolic_time(bpm.beat, resolution),
        BPM=bpm.bpm,
    )


@singledispatch
def load_symbolic_time(
    t: Union[int, Tuple[int, int, int]], resolution: int
) -> jbt.BeatsTime:
    ...


@load_symbolic_time.register
def load_symbolic_time_int(t: int, resolution: int) -> jbt.BeatsTime:
    return jbt.BeatsTime(t, resolution)


@load_symbolic_time.register(tuple)
def load_symbolic_time_tuple(t: Tuple[int, int, int], resolution: int) -> jbt.BeatsTime:
    return t[0] + jbt.BeatsTime(t[1], t[2])


@singledispatch
def load_note(note: memon.Note, resolution: int) -> Union[jbt.TapNote, jbt.LongNote]:
    ...


@load_note.register
def load_tap_note(note: memon.TapNote, resolution: int) -> jbt.TapNote:
    return jbt.TapNote(
        time=load_symbolic_time(note.t, resolution),
        position=jbt.NotePosition.from_index(note.n),
    )


@load_note.register
def load_long_note(note: memon.LongNote, resolution: int) -> jbt.LongNote:
    position = jbt.NotePosition.from_index(note.n)
    return jbt.LongNote(
        time=load_symbolic_time(note.t, resolution),
        position=position,
        duration=load_symbolic_time(note.l, resolution),
        tail_tip=convert_6_notation_to_position(position, note.p),
    )


def convert_6_notation_to_position(pos: jbt.NotePosition, p: int) -> jbt.NotePosition:
    # horizontal
    if p < 3:
        if p < pos.x:
            x = p
        else:
            x = p + 1
        y = pos.y
    else:
        p -= 3
        x = pos.x
        if p < pos.y:
            y = p
        else:
            y = p + 1

    return jbt.NotePosition(x, y)
