"""
Hypothesis strategies to generate notes and charts
"""

from decimal import Decimal
from enum import Flag, auto
from itertools import product
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Union

import hypothesis.strategies as st
from multidict import MultiDict

from jubeatools.song import (
    BeatsTime,
    BPMEvent,
    Chart,
    Difficulty,
    LongNote,
    Metadata,
    NotePosition,
    Preview,
    Song,
    TapNote,
    Timing,
)


@st.composite
def beat_time(
    draw: st.DrawFn,
    min_section: Optional[int] = None,
    max_section: Optional[int] = None,
    min_numerator: Optional[int] = None,
    max_numerator: Optional[int] = None,
    denominator_strat: st.SearchStrategy[int] = st.sampled_from([4, 8, 16, 3, 5]),
) -> BeatsTime:
    denominator = draw(denominator_strat)

    if min_section is not None:
        min_value = denominator * 4 * min_section
    else:
        min_value = 0

    if min_numerator is not None:
        min_value = max(min_value, min_numerator)

    if max_section is not None:
        max_value: Optional[int] = denominator * 4 * max_section
    else:
        max_value = None

    if max_numerator is not None:
        if max_value is not None:
            max_value = min(max_numerator, max_value)
        else:
            max_value = max_numerator

    numerator = draw(st.integers(min_value=min_value, max_value=max_value))
    return BeatsTime(numerator, denominator)


@st.composite
def note_position(draw: st.DrawFn) -> NotePosition:
    x = draw(st.integers(min_value=0, max_value=3))
    y = draw(st.integers(min_value=0, max_value=3))
    return NotePosition(x, y)


@st.composite
def tap_note(
    draw: st.DrawFn,
    time_strat: st.SearchStrategy[BeatsTime] = beat_time(max_section=10),
) -> TapNote:
    time = draw(time_strat)
    position = draw(note_position())
    return TapNote(time, position)


@st.composite
def long_note(
    draw: st.DrawFn,
    time_strat: st.SearchStrategy[BeatsTime] = beat_time(max_section=10),
    duration_strat: st.SearchStrategy[BeatsTime] = beat_time(
        min_numerator=1, max_section=3
    ),
) -> LongNote:
    time = draw(time_strat)
    position = draw(note_position())
    duration = draw(duration_strat)
    tail_is_vertical = draw(st.booleans())
    tail_offset = draw(st.integers(min_value=1, max_value=3))
    if tail_is_vertical:
        x = position.x
        y = (position.y + tail_offset) % 4
    else:
        x = (position.x + tail_offset) % 4
        y = position.y
    tail_tip = NotePosition(x, y)
    return LongNote(time, position, duration, tail_tip)


@st.composite
def bad_notes(draw: st.DrawFn, longs: bool) -> Set[Union[TapNote, LongNote]]:
    note_strat = tap_note()
    if longs:
        note_strat = st.one_of(note_strat, long_note())
    notes: Set[Union[TapNote, LongNote]] = draw(st.sets(note_strat, max_size=32))
    return notes


@st.composite
def notes(
    draw: st.DrawFn,
    collisions: bool = False,
    note_strat: st.SearchStrategy[Union[TapNote, LongNote]] = st.one_of(
        tap_note(), long_note()
    ),
    beat_time_strat: st.SearchStrategy[BeatsTime] = beat_time(max_section=3),
) -> Set[Union[TapNote, LongNote]]:
    raw_notes: Set[Union[TapNote, LongNote]] = draw(st.sets(note_strat, max_size=32))

    if collisions:
        return raw_notes
    else:
        last_notes: Dict[NotePosition, Optional[BeatsTime]] = {
            NotePosition(x, y): None for y, x in product(range(4), range(4))
        }
        notes: Set[Union[TapNote, LongNote]] = set()
        for note in sorted(raw_notes, key=lambda n: (n.time, n.position)):
            last_note_time = last_notes[note.position]
            if last_note_time is None:
                new_time = draw(beat_time_strat)
            else:
                numerator = draw(
                    st.integers(min_value=1, max_value=last_note_time.denominator * 4)
                )
                distance = BeatsTime(numerator, last_note_time.denominator)
                new_time = last_note_time + distance
            if isinstance(note, LongNote):
                notes.add(
                    LongNote(
                        time=new_time,
                        position=note.position,
                        duration=note.duration,
                        tail_tip=note.tail_tip,
                    )
                )
                last_notes[note.position] = new_time + note.duration
            else:
                notes.add(TapNote(time=new_time, position=note.position))
                last_notes[note.position] = new_time
        return notes


@st.composite
def bpms(draw: st.DrawFn) -> Decimal:
    d: Decimal = draw(st.decimals(min_value=1, max_value=1000, places=3))
    return d


@st.composite
def bpm_changes(
    draw: st.DrawFn,
    bpm_strat: st.SearchStrategy[Decimal] = bpms(),
    time_strat: st.SearchStrategy[BeatsTime] = beat_time(min_section=1, max_section=10),
) -> BPMEvent:
    time = draw(time_strat)
    bpm = draw(bpm_strat)
    return BPMEvent(time, bpm)


@st.composite
def timing_info(
    draw: st.DrawFn,
    with_bpm_changes: bool = True,
    bpm_strat: st.SearchStrategy[Decimal] = bpms(),
    beat_zero_offset_strat: st.SearchStrategy[Decimal] = st.decimals(
        min_value=0, max_value=20, places=3
    ),
    time_strat: st.SearchStrategy[BeatsTime] = beat_time(min_section=1, max_section=10),
) -> Timing:
    first_bpm = draw(bpm_strat)
    first_event = BPMEvent(BeatsTime(0), first_bpm)
    events = [first_event]
    if with_bpm_changes:
        raw_bpm_changes = st.lists(
            bpm_changes(bpm_strat, time_strat), unique_by=get_bpm_change_time
        )
        sorted_bpm_changes = raw_bpm_changes.map(
            lambda l: sorted(l, key=get_bpm_change_time)
        )
        other_events = draw(sorted_bpm_changes)
        events += other_events
    beat_zero_offset = draw(beat_zero_offset_strat)
    return Timing(events=events, beat_zero_offset=beat_zero_offset)


def get_bpm_change_time(b: BPMEvent) -> BeatsTime:
    return b.time


@st.composite
def level(draw: st.DrawFn) -> Union[int, Decimal]:
    d: Union[int, Decimal] = draw(
        st.one_of(
            st.integers(min_value=0), st.decimals(min_value=0, max_value=10.9, places=1)
        )
    )
    return d


@st.composite
def chart(
    draw: st.DrawFn,
    timing_strat: st.SearchStrategy[Timing] = timing_info(),
    notes_strat: st.SearchStrategy[Iterable[Union[TapNote, LongNote]]] = notes(),
    level_strat: st.SearchStrategy[Union[int, Decimal]] = level(),
) -> Chart:
    level = Decimal(draw(level_strat))
    timing = draw(timing_strat)
    notes = draw(notes_strat)
    return Chart(
        level=level,
        timing=timing,
        notes=sorted(notes, key=lambda n: (n.time, n.position)),
    )


@st.composite
def preview(draw: st.DrawFn) -> Preview:
    start = draw(
        st.decimals(min_value=0, allow_nan=False, allow_infinity=False, places=3)
    )
    length = draw(
        st.decimals(min_value=1, allow_nan=False, allow_infinity=False, places=3)
    )
    return Preview(start, length)


@st.composite
def metadata(
    draw: st.DrawFn,
    text_strat: st.SearchStrategy[str] = st.text(),
    path_strat: st.SearchStrategy[str] = st.text(),
) -> Metadata:
    return Metadata(
        title=draw(text_strat),
        artist=draw(text_strat),
        audio=Path(draw(path_strat)),
        cover=Path(draw(path_strat)),
        preview=draw(st.one_of(st.none(), preview())),
        preview_file=Path(draw(path_strat)),
    )


class TimingOption(Flag):
    GLOBAL = auto()
    PER_CHART = auto()
    BPM_CHANGES = auto()


@st.composite
def song(
    draw: st.DrawFn,
    diffs_strat: st.SearchStrategy[Set[str]] = st.sets(
        st.sampled_from(list(d.value for d in Difficulty)), min_size=1, max_size=3
    ),
    common_timing_strat: st.SearchStrategy[Optional[Timing]] = timing_info(),
    chart_strat: st.SearchStrategy[Chart] = chart(),
    metadata_strat: st.SearchStrategy[Metadata] = metadata(),
) -> Song:
    diffs = draw(diffs_strat)
    charts: MultiDict[Chart] = MultiDict()
    for diff_name in diffs:
        charts.add(diff_name, draw(chart_strat))

    return Song(
        metadata=draw(metadata_strat),
        charts=charts,
        common_timing=draw(common_timing_strat),
    )
