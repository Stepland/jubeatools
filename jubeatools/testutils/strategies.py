"""
Hypothesis strategies to generate notes and charts
"""
from decimal import Decimal
from enum import Enum, Flag, auto
from itertools import product
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union

import hypothesis.strategies as st
from multidict import MultiDict

from jubeatools.song import (
    BeatsTime,
    BPMEvent,
    Chart,
    LongNote,
    Metadata,
    NotePosition,
    Preview,
    Song,
    TapNote,
    Timing,
)
from jubeatools.testutils.typing import DrawFunc


@st.composite
def beat_time(
    draw: DrawFunc,
    min_section: Optional[int] = None,
    max_section: Optional[int] = None,
    min_numerator: Optional[int] = None,
    max_numerator: Optional[int] = None,
) -> BeatsTime:
    denominator = draw(st.sampled_from([4, 8, 16, 3, 5]))

    if min_section is not None:
        min_value = denominator * 4 * min_section
    else:
        min_value = 0

    if min_numerator is not None:
        min_value = max(min_value, min_numerator)

    if max_section is not None:
        max_value = denominator * 4 * max_section
    else:
        max_value = None

    if max_numerator is not None:
        max_value = (
            max_numerator if max_value is None else min(max_numerator, max_value)
        )

    numerator = draw(st.integers(min_value=min_value, max_value=max_value))
    return BeatsTime(numerator, denominator)


@st.composite
def note_position(draw: DrawFunc) -> NotePosition:
    x = draw(st.integers(min_value=0, max_value=3))
    y = draw(st.integers(min_value=0, max_value=3))
    return NotePosition(x, y)


@st.composite
def tap_note(draw: DrawFunc) -> TapNote:
    time = draw(beat_time(max_section=10))
    position = draw(note_position())
    return TapNote(time, position)


@st.composite
def long_note(draw: DrawFunc) -> LongNote:
    time = draw(beat_time(max_section=10))
    position = draw(note_position())
    duration = draw(beat_time(min_numerator=1, max_section=3))
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


class NoteOption(Flag):
    """What kind of notes are allowed to be generated"""

    # Long notes
    LONGS = auto()
    # Intersections between longs and other notes on the same square
    COLLISIONS = auto()


@st.composite
def bad_notes(draw: DrawFunc, longs: bool) -> Set[Union[TapNote, LongNote]]:
    note_strat = tap_note()
    if longs:
        note_strat = st.one_of(note_strat, long_note())
    notes: Set[Union[TapNote, LongNote]] = draw(st.sets(note_strat, max_size=32))
    return notes


@st.composite
def notes(draw: DrawFunc, options: NoteOption) -> Set[Union[TapNote, LongNote]]:
    if (NoteOption.COLLISIONS in options) and (NoteOption.LONGS not in options):
        raise ValueError("Can't ask for collisions without longs")

    note_strat = tap_note()
    if NoteOption.LONGS in options:
        note_strat = st.one_of(note_strat, long_note())
    raw_notes: Set[Union[TapNote, LongNote]] = draw(st.sets(note_strat, max_size=32))

    if NoteOption.COLLISIONS in options:
        return raw_notes
    else:
        last_notes: Dict[NotePosition, Optional[BeatsTime]] = {
            NotePosition(x, y): None for y, x in product(range(4), range(4))
        }
        notes: Set[Union[TapNote, LongNote]] = set()
        for note in sorted(raw_notes, key=lambda n: (n.time, n.position)):
            last_note_time = last_notes[note.position]
            if last_note_time is None:
                new_time = draw(beat_time(max_section=3))
            else:
                new_time = last_note_time + draw(
                    beat_time(min_numerator=1, max_section=3)
                )
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
def bpm_strat(draw: DrawFunc) -> Decimal:
    d: Decimal = draw(st.decimals(min_value=1, max_value=1000, places=3))
    return d


@st.composite
def bpm_change(draw: DrawFunc) -> BPMEvent:
    time = draw(beat_time(min_section=1, max_section=10))
    bpm = draw(bpm_strat())
    return BPMEvent(time, bpm)


@st.composite
def timing_info(draw: DrawFunc, bpm_changes: bool = True,) -> Timing:
    first_bpm = draw(bpm_strat())
    first_event = BPMEvent(BeatsTime(0), first_bpm)
    events = [first_event]
    if bpm_changes:
        raw_bpm_changes = st.lists(bpm_change(), unique_by=get_bpm_change_time)
        sorted_bpm_changes = raw_bpm_changes.map(
            lambda l: sorted(l, key=get_bpm_change_time)
        )
        other_events = draw(sorted_bpm_changes)
        events += other_events
    beat_zero_offset = draw(st.decimals(min_value=0, max_value=20, places=3))
    return Timing(events=events, beat_zero_offset=beat_zero_offset)


def get_bpm_change_time(b: BPMEvent) -> BeatsTime:
    return b.time


@st.composite
def chart(draw: DrawFunc, timing_strat: Any, notes_strat: Any) -> Chart:
    level = draw(st.integers(min_value=0))
    timing = draw(timing_strat)
    notes = draw(notes_strat)
    return Chart(
        level=level,
        timing=timing,
        notes=sorted(notes, key=lambda n: (n.time, n.position)),
    )


@st.composite
def preview(draw: DrawFunc) -> Preview:
    start = draw(
        st.decimals(min_value=0, allow_nan=False, allow_infinity=False, places=3)
    )
    length = draw(
        st.decimals(min_value=1, allow_nan=False, allow_infinity=False, places=3)
    )
    return Preview(start, length)


@st.composite
def metadata(draw: DrawFunc) -> Metadata:
    return Metadata(
        title=draw(st.text()),
        artist=draw(st.text()),
        audio=draw(st.text()),
        cover=draw(st.text()),
        preview=draw(st.one_of(st.none(), preview())),
    )


class TimingOption(Flag):
    GLOBAL = auto()
    PER_CHART = auto()
    BPM_CHANGES = auto()


@st.composite
def song(
    draw: DrawFunc,
    timing_options: TimingOption,
    extra_diffs: bool,
    notes_options: NoteOption,
) -> Song:
    if not ((TimingOption.GLOBAL | TimingOption.PER_CHART) & timing_options):
        raise ValueError(
            "Invalid timing options, at least one of the flags GLOBAL or PER_CHART must be set"
        )

    timing_strat = timing_info(TimingOption.BPM_CHANGES in timing_options)
    note_strat = notes(notes_options)
    diff_name_strat = st.sampled_from(["BSC", "ADV", "EXT"])
    if extra_diffs:
        # only go for ascii in extra diffs
        # https://en.wikipedia.org/wiki/Basic_Latin_(Unicode_block)
        diff_name_strat = st.one_of(
            diff_name_strat,
            st.text(
                alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
                min_size=1,
                max_size=20,
            ),
        )
    diffs = draw(st.sets(diff_name_strat, min_size=1, max_size=10))
    charts: MultiDict[Chart] = MultiDict()
    for diff_name in diffs:
        chart_timing_strat = st.none()
        if TimingOption.PER_CHART in timing_options:
            chart_timing_strat = st.one_of(st.none(), timing_strat)
        _chart = draw(chart(chart_timing_strat, note_strat))
        charts.add(diff_name, _chart)

    global_timing_start: st.SearchStrategy[Optional[Timing]] = st.none()
    if TimingOption.GLOBAL in timing_options:
        global_timing_start = timing_strat

    return Song(
        metadata=draw(metadata()),
        charts=charts,
        global_timing=draw(global_timing_start),
    )
