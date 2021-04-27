import pytest
from decimal import Decimal
from fractions import Fraction

from ..load_tools import decimal_to_beats


@pytest.mark.parametrize("numerator", range(240))
def test_fraction_recovery_after_rounding_to_three_decimals(numerator):
    fraction = Fraction(numerator, 240)
    decimal = numerator / Decimal(240)
    rounded = round(decimal, 3)
    text_form = str(rounded)
    re_parsed_decimal = Decimal(text_form)
    result = decimal_to_beats(re_parsed_decimal)
    assert fraction == result