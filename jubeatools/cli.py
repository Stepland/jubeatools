"""Command Line Interface"""
from pathlib import Path
from typing import Any, Dict, Optional

import click

from jubeatools.formats import DUMPERS, LOADERS
from jubeatools.formats.enum import JUBEAT_ANALYSER_FORMATS, Format
from jubeatools.formats.guess import guess_format


@click.command()
@click.argument("src", type=click.Path(exists=True, dir_okay=False))
@click.argument("dst", type=click.Path())
@click.option(
    "-f",
    "--format",
    "output_format",
    required=True,
    prompt="Choose an output format",
    type=click.Choice(list(f._value_ for f in DUMPERS.keys())),
    help="Output file format",
)
@click.option(
    "--circlefree",
    "circle_free",
    is_flag=True,
    help="Use #circlefree=1 for jubeat analyser formats",
)
def convert(
    src: str, dst: str, output_format: Format, **kwargs: Dict[str, Any]
) -> None:
    """Convert SRC to DST using the format specified by -f"""
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

    song = loader(Path(src))
    files = dumper(song, Path(dst), **kwargs)
    for path, contents in files.items():
        with path.open("wb") as f:
            f.write(contents)


if __name__ == "__main__":
    convert()
