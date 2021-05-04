from hypothesis import given
from hypothesis import strategies as st

from ..command import escape_string_value, unescape_string_value


@given(st.text())
def test_that_escaping_preserves_string(expected: str) -> None:
    escaped = escape_string_value(expected)
    actual = unescape_string_value(escaped)
    assert expected == actual
