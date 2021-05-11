from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import List, Union

from more_itertools import windowed
from sortedcontainers import SortedKeyList

from jubeatools import song
from jubeatools.formats.load_tools import round_beats
from jubeatools.utils import fraction_to_decimal, group_by


@dataclass
class BPMAtSecond:
    seconds: Fraction
    BPM: Fraction


@dataclass
class BPMChange:
    beats: song.BeatsTime
    seconds: Fraction
    BPM: Fraction


@dataclass
class TimeMap:
    """Wraps a song.Timing to allow converting symbolic time (in beats)
    to clock time (in seconds) and back"""

    beat_zero_offset: song.SecondsTime
    events_by_beats: SortedKeyList[BPMChange, song.BeatsTime]
    events_by_seconds: SortedKeyList[BPMChange, Fraction]

    @classmethod
    def from_timing(cls, beats: song.Timing) -> TimeMap:
        """Create a time map from a song.Timing object"""
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

        # set first BPM change then compute from there
        current_second = Fraction(beats.beat_zero_offset)
        bpm_changes = [
            BPMChange(first_event.time, current_second, Fraction(first_event.BPM))
        ]
        for previous, current in windowed(sorted_events, 2):
            if previous is None or current is None:
                continue

            beats_since_last_event = current.time - previous.time
            seconds_since_last_event = (60 * beats_since_last_event) / Fraction(
                previous.BPM
            )
            current_second += seconds_since_last_event
            bpm_change = BPMChange(current.time, current_second, Fraction(current.BPM))
            bpm_changes.append(bpm_change)

        return cls(
            beat_zero_offset=beats.beat_zero_offset,
            events_by_beats=SortedKeyList(bpm_changes, key=lambda b: b.beats),
            events_by_seconds=SortedKeyList(bpm_changes, key=lambda b: b.seconds),
        )

    @classmethod
    def from_seconds(cls, events: List[BPMAtSecond]) -> TimeMap:
        """Create a time map from a list of BPM changes with time positions
        given in seconds. The first BPM implicitely happens at beat zero"""
        if not events:
            raise ValueError("No BPM defined")

        grouped_by_time = group_by(events, key=lambda e: e.seconds)
        for time, events_at_time in grouped_by_time.items():
            if len(events_at_time) > 1:
                raise ValueError(f"Multiple BPMs defined at {time} seconds : {events}")

        # take the first BPM change then compute from there
        sorted_events = sorted(events, key=lambda e: e.seconds)
        first_event = sorted_events[0]
        current_beat = Fraction(0)
        bpm_changes = [BPMChange(current_beat, first_event.seconds, first_event.BPM)]
        for previous, current in windowed(sorted_events, 2):
            if previous is None or current is None:
                continue

            seconds_since_last_event = current.seconds - previous.seconds
            beats_since_last_event = (
                previous.BPM * seconds_since_last_event
            ) / Fraction(60)
            current_beat += beats_since_last_event
            bpm_change = BPMChange(current_beat, current.seconds, current.BPM)
            bpm_changes.append(bpm_change)

        return cls(
            beat_zero_offset=fraction_to_decimal(first_event.seconds),
            events_by_beats=SortedKeyList(bpm_changes, key=lambda b: b.beats),
            events_by_seconds=SortedKeyList(bpm_changes, key=lambda b: b.seconds),
        )

    def seconds_at(self, beat: song.BeatsTime) -> song.SecondsTime:
        frac_seconds = self.fractional_seconds_at(beat)
        return fraction_to_decimal(frac_seconds)

    def fractional_seconds_at(self, beat: song.BeatsTime) -> Fraction:
        if beat < 0:
            raise ValueError("Can't compute seconds at negative beat")

        # find previous bpm change
        index = self.events_by_beats.bisect_key_right(beat) - 1
        bpm_change: BPMChange = self.events_by_beats[index]

        # compute seconds since last bpm change
        beats_since_last_event = beat - bpm_change.beats
        seconds_since_last_event = (60 * beats_since_last_event) / bpm_change.BPM
        return bpm_change.seconds + seconds_since_last_event

    def beats_at(self, seconds: Union[song.SecondsTime, Fraction]) -> song.BeatsTime:
        if seconds < self.beat_zero_offset:
            raise ValueError(
                f"Can't compute beat time at {seconds} seconds, since it predates "
                f"beat zero, which happens at {self.beat_zero_offset} seconds"
            )

        # find previous bpm change
        frac_seconds = Fraction(seconds)
        index = self.events_by_seconds.bisect_key_right(frac_seconds) - 1
        bpm_change: BPMChange = self.events_by_seconds[index]

        # compute beats since last bpm change
        seconds_since_last_event = frac_seconds - bpm_change.seconds
        beats_since_last_event = (bpm_change.BPM * seconds_since_last_event) / Fraction(
            60
        )
        return bpm_change.beats + beats_since_last_event

    def convert_to_timing_info(self, beat_snap: int = 240) -> song.Timing:
        return song.Timing(
            events=[
                song.BPMEvent(
                    time=round_beats(e.beats, beat_snap),
                    BPM=fraction_to_decimal(e.BPM),
                )
                for e in self.events_by_beats
            ],
            beat_zero_offset=self.beat_zero_offset,
        )
