from functools import wraps
from importlib import resources

import pytest

from jubeatools.formats import LOADERS
from jubeatools.formats.guess import guess_format

from . import data


def test_RorataJins_example() -> None:
    with pytest.raises(SyntaxError, match="separator line"):
        with resources.path(data, "RorataJin's example.txt") as p:
            format_ = guess_format(p)
            loader = LOADERS[format_]
            song = loader(p)
