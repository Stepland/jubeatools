import json
import re
from pathlib import Path

from .enum import Format


def guess_format(path: Path) -> Format:
    if path.is_dir():
        raise ValueError("Can't guess chart format for a folder")

    try:
        return recognize_json_formats(path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        pass

    try:
        return recognize_jubeat_analyser_format(path)
    except (UnicodeDecodeError, ValueError):
        pass

    if looks_like_eve(path):
        return Format.EVE

    if looks_like_jbsq(path):
        return Format.JBSQ

    raise ValueError("Unrecognized file format")


def recognize_json_formats(path: Path) -> Format:
    with path.open() as f:
        obj = json.load(f)

    if not isinstance(obj, dict):
        raise ValueError("Top level value is not an object")

    if obj.keys() >= {"metadata", "data"}:
        return recognize_memon_version(obj)
    elif obj.keys() >= {"meta", "time", "note"}:
        return Format.MALODY
    else:
        raise ValueError("Unrecognized file format")


def recognize_memon_version(obj: dict) -> Format:
    try:
        version = obj["version"]
    except KeyError:
        return Format.MEMON_LEGACY

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
    with path.open(encoding="shift-jis-2004", errors="surrogateescape") as f:
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
        try:
            line = f.readline()
        except UnicodeDecodeError:
            return False

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


def looks_like_jbsq(path: Path) -> bool:
    magic = path.open(mode="rb").read(4)
    return magic in (b"IJBQ", b"IJSQ", b"JBSQ")
