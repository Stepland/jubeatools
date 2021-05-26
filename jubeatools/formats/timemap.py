from __future__ import annotations

from dataclasses import dataclass, replace
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
class BPMAtBeat:
    beats: Fraction
    BPM: Fraction


@dataclass
class SecondsAtBeat:
    seconds: Fraction
    beats: Fraction


@dataclass
class BPMChange:
    beats: song.BeatsTime
    seconds: Fraction
    BPM: Fraction


@dataclass
class TimeMap:
    """Wraps a song.Timing to allow converting symbolic time (in beats)
    to clock time (in seconds) and back"""

    events_by_beats: SortedKeyList[BPMChange, song.BeatsTime]
    events_by_seconds: SortedKeyList[BPMChange, Fraction]

    @classmethod
    def from_timing(cls, timing: song.Timing) -> TimeMap:
        """Create a time map from a song.Timing object"""
        return cls.from_beats(
            events=[
                BPMAtBeat(beats=e.time, BPM=Fraction(e.BPM)) for e in timing.events
            ],
            offset=SecondsAtBeat(
                seconds=Fraction(timing.beat_zero_offset), beats=Fraction(0)
            ),
        )

    @classmethod
    def from_beats(cls, events: List[BPMAtBeat], offset: SecondsAtBeat) -> TimeMap:
        """Create a time map from a list of BPM changes with times given in
        beats, the offset parameter is more flexible than a "regular" beat zero
        offset as it accepts non-zero beats"""
        if not events:
            raise ValueError("No BPM defined")

        grouped_by_time = group_by(events, key=lambda e: e.beats)
        for time, events_at_time in grouped_by_time.items():
            if len(events_at_time) > 1:
                raise ValueError(f"Multiple BPMs defined at beat {time} : {events}")

        # First compute everything as if the first BPM change happened at
        # zero seconds, then shift according to the offset
        sorted_events = sorted(events, key=lambda e: e.beats)
        first_event = sorted_events[0]
        current_second = Fraction(0)
        bpm_changes = [
            BPMChange(first_event.beats, current_second, Fraction(first_event.BPM))
        ]
        for previous, current in windowed(sorted_events, 2):
            if previous is None or current is None:
                continue

            beats_since_last_event = current.beats - previous.beats
            seconds_since_last_event = (60 * beats_since_last_event) / Fraction(
                previous.BPM
            )
            current_second += seconds_since_last_event
            bpm_change = BPMChange(current.beats, current_second, Fraction(current.BPM))
            bpm_changes.append(bpm_change)

        not_shifted = cls(
            events_by_beats=SortedKeyList(bpm_changes, key=lambda b: b.beats),
            events_by_seconds=SortedKeyList(bpm_changes, key=lambda b: b.seconds),
        )
        unshifted_seconds_at_offset = not_shifted.fractional_seconds_at(offset.beats)
        shift = offset.seconds - unshifted_seconds_at_offset
        shifted_bpm_changes = [
            replace(b, seconds=b.seconds + shift) for b in bpm_changes
        ]
        return cls(
            events_by_beats=SortedKeyList(shifted_bpm_changes, key=lambda b: b.beats),
            events_by_seconds=SortedKeyList(
                shifted_bpm_changes, key=lambda b: b.seconds
            ),
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
            events_by_beats=SortedKeyList(bpm_changes, key=lambda b: b.beats),
            events_by_seconds=SortedKeyList(bpm_changes, key=lambda b: b.seconds),
        )

    def seconds_at(self, beat: song.BeatsTime) -> song.SecondsTime:
        frac_seconds = self.fractional_seconds_at(beat)
        return fraction_to_decimal(frac_seconds)

    def fractional_seconds_at(self, beat: song.BeatsTime) -> Fraction:
        """Before the first bpm change, compute backwards from the first bpm,
        after the first bpm change, compute forwards from the previous bpm
        change"""
        index = self.events_by_beats.bisect_key_right(beat)
        first_or_previous_index = max(0, index - 1)
        bpm_change: BPMChange = self.events_by_beats[first_or_previous_index]
        beats_since_last_event = beat - bpm_change.beats
        seconds_since_last_event = (60 * beats_since_last_event) / bpm_change.BPM
        return bpm_change.seconds + seconds_since_last_event

    def beats_at(self, seconds: Union[song.SecondsTime, Fraction]) -> song.BeatsTime:
        frac_seconds = Fraction(seconds)
        index = self.events_by_seconds.bisect_key_right(frac_seconds)
        first_or_previous_index = max(0, index - 1)
        bpm_change: BPMChange = self.events_by_seconds[first_or_previous_index]
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
            beat_zero_offset=self.seconds_at(song.BeatsTime(0)),
        )
