from importlib import resources

from click.testing import CliRunner

from ..cli import convert
from . import data


def test_that_ommiting_beat_snap_works() -> None:
    """
    As pointed out by https://github.com/Stepland/jubeatools/issues/17
    """
    runner = CliRunner()
    with runner.isolated_filesystem(), resources.path(
        data, "Life Without You.eve"
    ) as p:
        result = runner.invoke(
            convert, [str(p.resolve(strict=True)), "out.txt", "-f", "memo2"]
        )
        assert result.exit_code == 0
