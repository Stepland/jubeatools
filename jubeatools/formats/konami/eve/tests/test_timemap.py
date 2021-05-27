from fractions import Fraction

from hypothesis import given

from jubeatools import song
from jubeatools.formats.timemap import TimeMap
from jubeatools.testutils import strategies as jbst
from jubeatools.utils import group_by


@given(jbst.timing_info(with_bpm_changes=True), jbst.beat_time())
def test_that_seconds_at_beat_works_like_the_naive_approach(
    timing: song.Timing, beat: song.BeatsTime
) -> None:
    time_map = TimeMap.from_timing(timing)
    expected = naive_approach(timing, beat)
    actual = time_map.fractional_seconds_at(beat)
    assert actual == expected


def naive_approach(beats: song.Timing, beat: song.BeatsTime) -> Fraction:
    if beat < 0:
        raise ValueError("Can't compute seconds at negative beat")

    if not beats.events:
        raise ValueError("No BPM defined")

    grouped_by_time = group_by(beats.events, key=lambda e: e.time)
    for time, events in grouped_by_time.items():
        if len(events) > 1:
            raise ValueError(f"Multiple BPMs defined on beat {time} : {events}")

    sorted_events = sorted(beats.events, key=lambda e: e.time)
    first_event = sorted_events[0]
    if first_event.time != song.BeatsTime(0):
        raise ValueError("First BPM event is not on beat zero")

    if beat > sorted_events[-1].time:
        events_before = sorted_events
    else:
        last_index = next(i for i, e in enumerate(sorted_events) if e.time >= beat)
        events_before = sorted_events[:last_index]
    total_seconds = Fraction(0)
    current_beat = beat
    for event in reversed(events_before):
        beats_since_previous = current_beat - event.time
        seconds_since_previous = (60 * beats_since_previous) / Fraction(event.BPM)
        total_seconds += seconds_since_previous
        current_beat = event.time

    total_seconds = total_seconds + Fraction(beats.beat_zero_offset)
    return total_seconds
