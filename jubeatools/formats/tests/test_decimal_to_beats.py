from decimal import Decimal
from fractions import Fraction

import pytest

from ..load_tools import round_beats


@pytest.mark.parametrize("numerator", range(240))
def test_fraction_recovery_after_rounding_to_three_decimals(numerator: int) -> None:
    fraction = Fraction(numerator, 240)
    decimal = numerator / Decimal(240)
    rounded = round(decimal, 3)
    text_form = str(rounded)
    re_parsed_decimal = Decimal(text_form)
    result = round_beats(re_parsed_decimal)
    assert fraction == result
