import json
import re
from pathlib import Path

from .enum import Format


def guess_format(path: Path) -> Format:
    if path.is_dir():
        raise ValueError("Can't guess chart format for a folder")

    try:
        return recognize_memon_version(path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        pass

    try:
        return recognize_jubeat_analyser_format(path)
    except (UnicodeDecodeError, ValueError):
        pass

    if looks_like_eve(path):
        return Format.EVE

    raise ValueError("Unrecognized file format")


def recognize_memon_version(path: Path) -> Format:
    with path.open() as f:
        obj = json.load(f)

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


def recognize_jubeat_analyser_format(path: Path) -> Format:
    with path.open(encoding="shift-jis-2004") as f:
        lines = f.readlines()

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


def looks_like_eve(path: Path) -> bool:
    with path.open(encoding="ascii") as f:
        line = f.readline()
        if line.strip():
            return looks_like_eve_line(next(f))

    return False


EVE_COMMANDS = {
    "END",
    "MEASURE",
    "HAKU",
    "PLAY",
    "LONG",
    "TEMPO",
}


def looks_like_eve_line(line: str) -> bool:
    columns = line.split(",")
    if len(columns) != 3:
        return False

    raw_tick, raw_command, raw_value = map(str.strip, columns)
    try:
        int(raw_tick)
    except Exception:
        return False

    if raw_command not in EVE_COMMANDS:
        return False

    try:
        int(raw_value)
    except Exception:
        return False

    return True
