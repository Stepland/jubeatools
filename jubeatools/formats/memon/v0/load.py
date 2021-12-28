from pathlib import Path
from typing import Any, Dict, Union

from jubeatools import song as jbt
from jubeatools.utils import none_or

from ..tools import make_memon_folder_loader
from . import schema as memon


def _load_memon_note_v0(
    note: dict, resolution: int
) -> Union[jbt.TapNote, jbt.LongNote]:
    position = jbt.NotePosition.from_index(note["n"])
    time = jbt.beats_time_from_ticks(ticks=note["t"], resolution=resolution)
    if note["l"] > 0:
        duration = jbt.beats_time_from_ticks(ticks=note["l"], resolution=resolution)
        p_value = note["p"]
        𝛿x, 𝛿y = memon.P_VALUE_TO_X_Y_OFFSET[p_value]
        tail_tip = jbt.NotePosition.from_raw_position(position + jbt.Position(𝛿x, 𝛿y))
        return jbt.LongNote(time, position, duration, tail_tip)
    else:
        return jbt.TapNote(time, position)


def _load_memon_legacy(raw_memon: Any) -> jbt.Song:
    schema = memon.Memon_legacy()
    file = schema.load(raw_memon)
    metadata = jbt.Metadata(
        title=file["metadata"]["title"],
        artist=file["metadata"]["artist"],
        audio=Path(file["metadata"]["audio"]),
        cover=Path(file["metadata"]["cover"]),
    )
    common_timing = jbt.Timing(
        events=[jbt.BPMEvent(time=jbt.BeatsTime(0), BPM=file["metadata"]["BPM"])],
        beat_zero_offset=jbt.SecondsTime(-file["metadata"]["offset"]),
    )
    charts: Dict[str, jbt.Chart] = {}
    for memon_chart in file["data"]:
        difficulty = memon_chart["dif_name"]
        chart = jbt.Chart(
            level=memon_chart["level"],
            notes=[
                _load_memon_note_v0(note, memon_chart["resolution"])
                for note in memon_chart["notes"]
            ],
        )
        charts[difficulty] = chart

    return jbt.Song(metadata=metadata, charts=charts, common_timing=common_timing)


load_memon_legacy = make_memon_folder_loader(_load_memon_legacy)


def _load_memon_0_1_0(raw_memon: Any) -> jbt.Song:
    schema = memon.Memon_0_1_0()
    file = schema.load(raw_memon)
    metadata = jbt.Metadata(
        title=file["metadata"]["title"],
        artist=file["metadata"]["artist"],
        audio=Path(file["metadata"]["audio"]),
        cover=Path(file["metadata"]["cover"]),
    )
    common_timing = jbt.Timing(
        events=[jbt.BPMEvent(time=jbt.BeatsTime(0), BPM=file["metadata"]["BPM"])],
        beat_zero_offset=jbt.SecondsTime(-file["metadata"]["offset"]),
    )
    charts: Dict[str, jbt.Chart] = {}
    for difficulty, memon_chart in file["data"].items():
        chart = jbt.Chart(
            level=memon_chart["level"],
            notes=[
                _load_memon_note_v0(note, memon_chart["resolution"])
                for note in memon_chart["notes"]
            ],
        )
        charts[difficulty] = chart

    return jbt.Song(metadata=metadata, charts=charts, common_timing=common_timing)


load_memon_0_1_0 = make_memon_folder_loader(_load_memon_0_1_0)


def _load_memon_0_2_0(raw_memon: Any) -> jbt.Song:
    schema = memon.Memon_0_2_0()
    file = schema.load(raw_memon)
    preview = None
    if "preview" in file["metadata"]:
        start = file["metadata"]["preview"]["position"]
        length = file["metadata"]["preview"]["length"]
        preview = jbt.Preview(start, length)

    metadata = jbt.Metadata(
        title=file["metadata"]["title"],
        artist=file["metadata"]["artist"],
        audio=Path(file["metadata"]["audio"]),
        cover=Path(file["metadata"]["cover"]),
        preview=preview,
    )
    common_timing = jbt.Timing(
        events=[jbt.BPMEvent(time=jbt.BeatsTime(0), BPM=file["metadata"]["BPM"])],
        beat_zero_offset=jbt.SecondsTime(-file["metadata"]["offset"]),
    )
    charts: Dict[str, jbt.Chart] = {}
    for difficulty, memon_chart in file["data"].items():
        chart = jbt.Chart(
            level=memon_chart["level"],
            notes=[
                _load_memon_note_v0(note, memon_chart["resolution"])
                for note in memon_chart["notes"]
            ],
        )
        charts[difficulty] = chart

    return jbt.Song(metadata=metadata, charts=charts, common_timing=common_timing)


load_memon_0_2_0 = make_memon_folder_loader(_load_memon_0_2_0)


def _load_memon_0_3_0(raw_memon: Any) -> jbt.Song:
    schema = memon.Memon_0_3_0()
    file = schema.load(raw_memon)
    preview = None
    if "preview" in file["metadata"]:
        start = file["metadata"]["preview"]["position"]
        length = file["metadata"]["preview"]["length"]
        preview = jbt.Preview(start, length)

    metadata = jbt.Metadata(
        title=file["metadata"]["title"],
        artist=file["metadata"]["artist"],
        audio=none_or(Path, file["metadata"].get("audio")),
        cover=none_or(Path, file["metadata"].get("cover")),
        preview=preview,
        preview_file=none_or(Path, file["metadata"].get("preview_path")),
    )
    common_timing = jbt.Timing(
        events=[jbt.BPMEvent(time=jbt.BeatsTime(0), BPM=file["metadata"]["BPM"])],
        beat_zero_offset=jbt.SecondsTime(-file["metadata"]["offset"]),
    )
    charts: Dict[str, jbt.Chart] = {}
    for difficulty, memon_chart in file["data"].items():
        chart = jbt.Chart(
            level=memon_chart["level"],
            notes=[
                _load_memon_note_v0(note, memon_chart["resolution"])
                for note in memon_chart["notes"]
            ],
        )
        charts[difficulty] = chart

    return jbt.Song(metadata=metadata, charts=charts, common_timing=common_timing)


load_memon_0_3_0 = make_memon_folder_loader(_load_memon_0_3_0)
