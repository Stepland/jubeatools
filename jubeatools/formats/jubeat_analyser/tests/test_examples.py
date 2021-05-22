from importlib import resources

import pytest

from jubeatools.formats import LOADERS
from jubeatools.formats.guess import guess_format

from . import data


def test_RorataJins_example() -> None:
    """This file has a #memo tag but actually uses mono-column formatting,
    Here I just check that a friendlier error message is sent because there
    is not much else I can to do here, the file is plain old wrong"""
    with pytest.raises(SyntaxError, match="separator line"):
        with resources.path(data, "RorataJin's example.txt") as p:
            format_ = guess_format(p)
            loader = LOADERS[format_]
            _ = loader(p)

def test_Booths_of_Fighters_memo() -> None:
    """This file has 2 quirks my code did not anticipate :
    - while it's in #memo2 format, it actually uses b= and t= commands
    - the position and timing parts are separated by some less common
      whitespace character"""
    with resources.path(data, "Booths_of_Fighters_memo.txt") as p:
        format_ = guess_format(p)
        loader = LOADERS[format_]
        _ = loader(p)
