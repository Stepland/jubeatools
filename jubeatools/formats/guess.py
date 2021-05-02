import json
import re
from pathlib import Path
from typing import Any, List

from .enum import Format


def guess_format(path: Path) -> Format:
    if path.is_dir():
        raise ValueError("Can't guess chart format for a folder")

    # The file is valid json => memon
    try:
        with path.open() as f:
            obj = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    else:
        return guess_memon_version(obj)

    # The file is valid shift-jis-2004 => jubeat analyser
    try:
        with path.open(encoding="shift-jis-2004") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        pass
    else:
        return guess_jubeat_analyser_format(lines)

    raise ValueError("Unrecognized file format")


def guess_memon_version(obj: Any) -> Format:
    try:
        version = obj["version"]
    except KeyError:
        return Format.MEMON_LEGACY
    except TypeError:
        raise ValueError(
            "This JSON file is not a correct memon file : the top-level "
            "value is not an object"
        )

    if version == "0.1.0":
        return Format.MEMON_0_1_0
    elif version == "0.2.0":
        return Format.MEMON_0_2_0
    else:
        raise ValueError(f"Unsupported memon version : {version}")


JUBEAT_ANALYSER_COMMANDS = {
    "b",
    "m",
    "o",
    "r",
    "t",
    "#lev",
    "#dif",
    "#title",
    "#artist",
}

COMMENT = re.compile(r"//.*")


def _dirty_jba_line_strip(line: str) -> str:
    """This does not deal with '//' in quotes properly,
    thankfully we don't care when looking for an argument-less command"""
    return COMMENT.sub("", line).strip()


def guess_jubeat_analyser_format(lines: List[str]) -> Format:
    saw_jubeat_analyser_commands = False
    for raw_line in lines:
        line = _dirty_jba_line_strip(raw_line)
        if line in ("#memo2", "#boogie"):
            return Format.MEMO_2
        elif line == "#memo1":
            return Format.MEMO_1
        elif line == "#memo":
            return Format.MEMO
        elif "=" in line:
            index = line.index("=")
            if line[:index] in JUBEAT_ANALYSER_COMMANDS:
                saw_jubeat_analyser_commands = True

    if saw_jubeat_analyser_commands:
        return Format.MONO_COLUMN
    else:
        raise ValueError("Unrecognized file format")
