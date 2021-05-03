from hypothesis import given
from hypothesis import strategies as st

from ..command import dump_value, parse_value


@given(st.text())
def test_that_strings_roundtrip(expected: str) -> None:
    dumped = dump_value(expected)
    actual = parse_value(dumped)
    assert expected == actual
