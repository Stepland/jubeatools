from decimal import Decimal

from hypothesis import given

from jubeatools.song import BeatsTime, BPMEvent, Chart, Metadata, SecondsTime, Timing
from jubeatools.testutils.strategies import NoteOption
from jubeatools.testutils.strategies import notes as notes_strat

from ..mono_column.dump import _dump_mono_column_chart
from ..mono_column.load import MonoColumnParser


@given(notes_strat(NoteOption.LONGS))
def test_many_notes(notes):
    ...