"""Command Line Interface"""

from pathlib import Path
from typing import Any, Dict, Optional

import click

from jubeatools.formats import DUMPERS, LOADERS
from jubeatools.formats.enum import Format
from jubeatools.formats.guess import guess_format

from .helpers import dumper_option, loader_option


@click.command()
@click.argument("src", type=click.Path(exists=True, dir_okay=False))
@click.argument("dst", type=click.Path())
@click.option(
    "--input-format",
    "input_format",
    type=click.Choice(list(f._value_ for f in LOADERS.keys())),
    help="Input file format",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    required=True,
    prompt="Choose an output format",
    type=click.Choice(list(f._value_ for f in DUMPERS.keys())),
    help="Output file format",
)
@dumper_option(
    "--circlefree",
    "circle_free",
    is_flag=True,
    help="Use #circlefree=1 for jubeat analyser formats",
)
@loader_option(
    "--beat-snap",
    "beat_snap",
    type=click.IntRange(min=1),
    help=(
        "For compatible input formats, snap all notes and bpm changes to "
        "the nearest 1/beat_snap beat"
    ),
)
def convert(
    src: str,
    dst: str,
    input_format: Optional[Format],
    output_format: Format,
    loader_options: Optional[Dict[str, Any]] = None,
    dumper_options: Optional[Dict[str, Any]] = None,
) -> None:
    """Convert SRC to DST using the format specified by -f"""
    if input_format is None:
        input_format = guess_format(Path(src))
        click.echo(f"Detected input file format : {input_format}")

    try:
        loader = LOADERS[input_format]
    except KeyError:
        raise ValueError(f"Unsupported input format : {input_format}")

    try:
        dumper = DUMPERS[output_format]
    except KeyError:
        raise ValueError(f"Unsupported output format : {input_format}")

    loader_options = loader_options or {}
    song = loader(Path(src), **loader_options)
    dumper_options = dumper_options or {}
    files = dumper(song, Path(dst), **dumper_options)
    for path, contents in files.items():
        with path.open("wb") as f:
            f.write(contents)


if __name__ == "__main__":
    convert()
