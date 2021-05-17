import math

from hypothesis import given
from hypothesis import strategies as st

from jubeatools.formats.konami.commons import bpm_to_value, value_to_truncated_bpm


@given(st.integers(min_value=1, max_value=6 * 10 ** 7))
def test_that_truncating_preserves_tempo_value(original_value: int) -> None:
    truncated_bpm = value_to_truncated_bpm(original_value)
    raw_recovered_value = bpm_to_value(truncated_bpm)
    recovered_value = math.floor(raw_recovered_value)
    assert recovered_value == original_value
