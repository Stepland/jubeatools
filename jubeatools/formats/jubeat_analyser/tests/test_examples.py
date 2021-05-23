from importlib import resources

import pytest

from jubeatools.formats import LOADERS
from jubeatools.formats.guess import guess_format

from . import data


def try_to_load(example_file: str) -> None:
    with resources.path(data, example_file) as p:
        format_ = guess_format(p)
        loader = LOADERS[format_]
        _ = loader(p)


def test_RorataJins_example() -> None:
    """This file has a #memo tag but actually uses mono-column formatting,
    Here I just check that a friendlier error message is sent because there
    is not much else I can to do here, the file is plain old wrong"""
    with pytest.raises(SyntaxError, match="separator line"):
        try_to_load("RorataJin's example.txt")


def test_Booths_of_Fighters_memo() -> None:
    """This file has 2 quirks my code did not anticipate :
    - while it's in #memo2 format, it actually uses b= and t= commands
    - the position and timing parts are separated by some less common
      whitespace character"""
    try_to_load("Booths_of_Fighters_memo.txt")


def test_MTC_Nageki_no_Ki_EXT() -> None:
    """This file is proper euc-kr text that's specially crafted to also be
    compatible with jubeat analyser, handcrafted mojibake and all"""
    try_to_load("MTC_Nageki_no_Ki_EXT.txt")


def test_MTC_Mimi_EXT() -> None:
    """Also an euc-kr file but also has long notes"""
    try_to_load("MTC_Mimi_EXT.txt")
