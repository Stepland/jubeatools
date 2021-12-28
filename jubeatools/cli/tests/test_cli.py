from importlib import resources
from pathlib import Path

from click.testing import CliRunner

from jubeatools import song as jbt
from jubeatools.formats import LOADERS, Format

from ..cli import convert
from . import data


def test_that_ommiting_beat_snap_works() -> None:
    """As pointed out by https://github.com/Stepland/jubeatools/issues/17"""
    runner = CliRunner()
    with runner.isolated_filesystem(), resources.path(
        data, "Life Without You.eve"
    ) as p:
        result = runner.invoke(
            convert, [str(p.resolve(strict=True)), "out.txt", "-f", "memo2"]
        )
        if result.exception:
            raise result.exception
        assert result.exit_code == 0


def test_that_is_flag_works_the_way_intended() -> None:
    """It's unclear to me what the default value is for an option with
    is_flag=True"""
    with resources.path(data, "Life Without You.eve") as p:
        called_with_the_flag = convert.make_context(
            "convert",
            [str(p.resolve(strict=True)), "out.txt", "-f", "memo2", "--circlefree"],
        )
        assert called_with_the_flag.params["dumper_options"]["circle_free"] is True

        called_without_the_flag = convert.make_context(
            "convert", [str(p.resolve(strict=True)), "out.txt", "-f", "memo2"]
        )
        dumper_options = called_without_the_flag.params.get("dumper_options")
        if dumper_options is not None:
            circle_free = dumper_options.get("circle_free")
            assert not circle_free


def test_that_the_merge_option_works_for_memon_files() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(), resources.path(data, "memon_merge") as p:
        result = runner.invoke(
            convert,
            [
                "--input-format",
                "memon:v0.1.0",
                str(p.resolve(strict=True)),
                "--merge",
                "out.memon",
                "-f",
                "memon:v0.1.0",
            ],
        )
        if result.exception:
            raise result.exception
        assert result.exit_code == 0

        memon_loader = LOADERS[Format.MEMON_0_1_0]
        bsc = memon_loader(p / "Sky Bus For Hire BSC.memon")
        adv = memon_loader(p / "Sky Bus For Hire ADV.memon")
        ext = memon_loader(p / "Sky Bus For Hire EXT.memon")
        merged_by_cli = LOADERS[Format.MEMON_0_1_0](Path("out.memon"))
        merged_with_python = jbt.Song.from_monochart_instances(bsc, adv, ext)
        assert merged_by_cli == merged_with_python
