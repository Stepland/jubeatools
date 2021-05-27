from importlib import resources

from jubeatools.formats import LOADERS
from jubeatools.formats.guess import guess_format

from . import data


def try_to_load(example_file: str) -> None:
    with resources.path(data, example_file) as p:
        format_ = guess_format(p)
        loader = LOADERS[format_]
        _ = loader(p)


def test_MilK() -> None:
    """An actual malody chart will have may keys unspecified in the marshmallow
    schema, these should be ignored"""
    try_to_load("1533908574.mc")
