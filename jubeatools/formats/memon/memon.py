from io import StringIO
from itertools import chain
from pathlib import Path
from typing import Any, Dict, List, Union

import simplejson as json
from marshmallow import (
    RAISE,
    Schema,
    ValidationError,
    fields,
    validate,
    validates_schema,
)
from multidict import MultiDict

from jubeatools import song as jbt
from jubeatools.utils import lcm

# v0.x.x long note value :
#
#         8
#         4
#         0
#  11 7 3 . 1 5 9
#         2
#         6
#        10

X_Y_OFFSET_TO_P_VALUE = {
    (0, -1): 0,
    (0, -2): 4,
    (0, -3): 8,
    (0, 1): 2,
    (0, 2): 6,
    (0, 3): 10,
    (1, 0): 1,
    (2, 0): 5,
    (3, 0): 9,
    (-1, 0): 3,
    (-2, 0): 7,
    (-3, 0): 11,
}

P_VALUE_TO_X_Y_OFFSET = {v: k for k, v in X_Y_OFFSET_TO_P_VALUE.items()}


class StrictSchema(Schema):
    class Meta:
        unknown = RAISE


class MemonNote(StrictSchema):
    n = fields.Integer(required=True, validate=validate.Range(min=0, max=15))
    t = fields.Integer(required=True, validate=validate.Range(min=0))
    l = fields.Integer(required=True, validate=validate.Range(min=0))
    p = fields.Integer(required=True, validate=validate.Range(min=0, max=11))

    @validates_schema
    def validate_tail_tip_position(self, data: Dict[str, int], **kwargs: Any) -> None:
        if data["l"] > 0:
            x = data["n"] % 4
            y = data["n"] // 4
            dx, dy = P_VALUE_TO_X_Y_OFFSET[data["p"]]
            if not (0 <= x + dx < 4 and 0 <= y + dy < 4):
                raise ValidationError("Invalid tail position : {data}")


class MemonChart_0_1_0(StrictSchema):
    level = fields.Decimal(required=True)
    resolution = fields.Integer(required=True, validate=validate.Range(min=1))
    notes = fields.Nested(MemonNote, many=True)


class MemonChart_legacy(MemonChart_0_1_0):
    dif_name = fields.String(required=True)


class MemonMetadata_legacy(StrictSchema):
    title = fields.String(required=True, data_key="song title")
    artist = fields.String(required=True)
    audio = fields.String(required=True, data_key="music path")
    cover = fields.String(required=True, data_key="jacket path")
    BPM = fields.Decimal(
        required=True, validate=validate.Range(min=0, min_inclusive=False)
    )
    offset = fields.Decimal(required=True)


class MemonMetadata_0_1_0(MemonMetadata_legacy):
    cover = fields.String(required=True, data_key="album cover path")


class MemonPreview(StrictSchema):
    position = fields.Decimal(required=True, validate=validate.Range(min=0))
    length = fields.Decimal(
        required=True, validate=validate.Range(min=0, min_inclusive=False)
    )


class MemonMetadata_0_2_0(MemonMetadata_0_1_0):
    preview = fields.Nested(MemonPreview)


class Memon_legacy(StrictSchema):
    metadata = fields.Nested(MemonMetadata_legacy, required=True)
    data = fields.Nested(MemonChart_legacy, required=True, many=True)


class Memon_0_1_0(StrictSchema):
    version = fields.String(required=True, validate=validate.OneOf(["0.1.0"]))
    metadata = fields.Nested(MemonMetadata_0_1_0, required=True)
    data = fields.Dict(
        keys=fields.String(), values=fields.Nested(MemonChart_0_1_0), required=True
    )


class Memon_0_2_0(StrictSchema):
    version = fields.String(required=True, validate=validate.OneOf(["0.2.0"]))
    metadata = fields.Nested(MemonMetadata_0_2_0, required=True)
    data = fields.Dict(
        keys=fields.String(), values=fields.Nested(MemonChart_0_1_0), required=True
    )


def _load_raw_memon(file: Path) -> Dict[str, Any]:
    with open(file) as f:
        res = json.load(f, use_decimal=True)
        if not isinstance(res, dict):
            raise ValueError(
                "JSON file does not represent a valid memon file : "
                "The top level of a memon file should be a JSON Object"
            )
        return res


def _load_memon_note_v0(
    note: dict, resolution: int
) -> Union[jbt.TapNote, jbt.LongNote]:
    position = jbt.NotePosition.from_index(note["n"])
    time = jbt.beats_time_from_ticks(ticks=note["t"], resolution=resolution)
    if note["l"] > 0:
        duration = jbt.beats_time_from_ticks(ticks=note["l"], resolution=resolution)
        p_value = note["p"]
        𝛿x, 𝛿y = P_VALUE_TO_X_Y_OFFSET[p_value]
        tail_tip = jbt.NotePosition.from_raw_position(position + jbt.Position(𝛿x, 𝛿y))
        return jbt.LongNote(time, position, duration, tail_tip)
    else:
        return jbt.TapNote(time, position)


def load_memon_legacy(path: Path, **kwargs: Any) -> jbt.Song:
    raw_memon = _load_raw_memon(path)
    schema = Memon_legacy()
    memon = schema.load(raw_memon)
    metadata = jbt.Metadata(
        title=memon["metadata"]["title"],
        artist=memon["metadata"]["artist"],
        audio=Path(memon["metadata"]["audio"]),
        cover=Path(memon["metadata"]["cover"]),
    )
    common_timing = jbt.Timing(
        events=[jbt.BPMEvent(time=jbt.BeatsTime(0), BPM=memon["metadata"]["BPM"])],
        beat_zero_offset=jbt.SecondsTime(-memon["metadata"]["offset"]),
    )
    charts: MultiDict[jbt.Chart] = MultiDict()
    for memon_chart in memon["data"]:
        charts.add(
            memon_chart["dif_name"],
            jbt.Chart(
                level=memon_chart["level"],
                notes=[
                    _load_memon_note_v0(note, memon_chart["resolution"])
                    for note in memon_chart["notes"]
                ],
            ),
        )

    return jbt.Song(metadata=metadata, charts=charts, common_timing=common_timing)


def load_memon_0_1_0(path: Path, **kwargs: Any) -> jbt.Song:
    raw_memon = _load_raw_memon(path)
    schema = Memon_0_1_0()
    memon = schema.load(raw_memon)
    metadata = jbt.Metadata(
        title=memon["metadata"]["title"],
        artist=memon["metadata"]["artist"],
        audio=Path(memon["metadata"]["audio"]),
        cover=Path(memon["metadata"]["cover"]),
    )
    common_timing = jbt.Timing(
        events=[jbt.BPMEvent(time=jbt.BeatsTime(0), BPM=memon["metadata"]["BPM"])],
        beat_zero_offset=jbt.SecondsTime(-memon["metadata"]["offset"]),
    )
    charts: MultiDict[jbt.Chart] = MultiDict()
    for difficulty, memon_chart in memon["data"].items():
        charts.add(
            difficulty,
            jbt.Chart(
                level=memon_chart["level"],
                notes=[
                    _load_memon_note_v0(note, memon_chart["resolution"])
                    for note in memon_chart["notes"]
                ],
            ),
        )

    return jbt.Song(metadata=metadata, charts=charts, common_timing=common_timing)


def load_memon_0_2_0(path: Path, **kwargs: Any) -> jbt.Song:
    raw_memon = _load_raw_memon(path)
    schema = Memon_0_2_0()
    memon = schema.load(raw_memon)
    preview = None
    if "preview" in memon["metadata"]:
        start = memon["metadata"]["preview"]["position"]
        length = memon["metadata"]["preview"]["length"]
        preview = jbt.Preview(start, length)

    metadata = jbt.Metadata(
        title=memon["metadata"]["title"],
        artist=memon["metadata"]["artist"],
        audio=Path(memon["metadata"]["audio"]),
        cover=Path(memon["metadata"]["cover"]),
        preview=preview,
    )
    common_timing = jbt.Timing(
        events=[jbt.BPMEvent(time=jbt.BeatsTime(0), BPM=memon["metadata"]["BPM"])],
        beat_zero_offset=jbt.SecondsTime(-memon["metadata"]["offset"]),
    )
    charts: MultiDict[jbt.Chart] = MultiDict()
    for difficulty, memon_chart in memon["data"].items():
        charts.add(
            difficulty,
            jbt.Chart(
                level=memon_chart["level"],
                notes=[
                    _load_memon_note_v0(note, memon_chart["resolution"])
                    for note in memon_chart["notes"]
                ],
            ),
        )

    return jbt.Song(metadata=metadata, charts=charts, common_timing=common_timing)


def _long_note_tail_value_v0(note: jbt.LongNote) -> int:
    dx = note.tail_tip.x - note.position.x
    dy = note.tail_tip.y - note.position.y
    try:
        return X_Y_OFFSET_TO_P_VALUE[dx, dy]
    except KeyError:
        raise ValueError(
            f"memon cannot represent a long note with its tail starting ({dx}, {dy}) away from the note"
        ) from None


def _get_timing(song: jbt.Song) -> jbt.Timing:
    if song.common_timing is not None:
        return song.common_timing
    else:
        return next(
            chart.timing for chart in song.charts.values() if chart.timing is not None
        )


def _raise_if_unfit_for_v0(song: jbt.Song, version: str) -> None:

    """Raises an exception if the Song object is ill-formed or contains information
    that cannot be represented in a memon v0.x.y file (includes legacy)"""

    if song.common_timing is None and all(
        chart.timing is None for chart in song.charts.values()
    ):
        raise ValueError("The song has no timing information")

    chart_timings = [
        chart.timing for chart in song.charts.values() if chart.timing is not None
    ]

    if chart_timings:
        first_one = chart_timings[0]
        if any(t != first_one for t in chart_timings):
            raise ValueError(
                f"memon:{version} cannot represent a song with per-chart timing"
            )

    timing = _get_timing(song)
    number_of_timing_events = len(timing.events)
    if number_of_timing_events != 1:
        if number_of_timing_events == 0:
            raise ValueError("The song has no BPM")
        else:
            raise ValueError(f"memon:{version} does not handle BPM changes")

    event = timing.events[0]
    if event.BPM <= 0:
        raise ValueError(f"memon:{version} only accepts strictly positive BPMs")

    if event.time != 0:
        raise ValueError(f"memon:{version} only accepts a BPM on the first beat")

    for difficulty, chart in song.charts.items():
        if len(set(chart.notes)) != len(chart.notes):
            raise ValueError(
                f"{difficulty} chart has duplicate notes, these cannot be represented"
            )


def _dump_to_json(memon: dict) -> bytes:
    memon_fp = StringIO()
    json.dump(memon, memon_fp, use_decimal=True, indent=4)
    return memon_fp.getvalue().encode("utf-8")


def _compute_resolution(notes: List[Union[jbt.TapNote, jbt.LongNote]]) -> int:
    return lcm(
        *chain(
            iter(note.time.denominator for note in notes),
            iter(
                note.duration.denominator
                for note in notes
                if isinstance(note, jbt.LongNote)
            ),
        )
    )


def _dump_memon_note_v0(
    note: Union[jbt.TapNote, jbt.LongNote], resolution: int
) -> Dict[str, int]:
    """converts a note into the {n, t, l, p} form"""
    memon_note = {
        "n": note.position.index,
        "t": note.time.numerator * (resolution // note.time.denominator),
        "l": 0,
        "p": 0,
    }
    if isinstance(note, jbt.LongNote):
        memon_note["l"] = note.duration.numerator * (
            resolution // note.duration.denominator
        )
        memon_note["p"] = _long_note_tail_value_v0(note)

    return memon_note


def dump_memon_legacy(song: jbt.Song, path: Path, **kwargs: dict) -> Dict[Path, bytes]:

    _raise_if_unfit_for_v0(song, "legacy")
    timing = _get_timing(song)

    memon: Dict[str, Any] = {
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "jacket path": str(song.metadata.cover),
            "BPM": timing.events[0].BPM,
            "offset": -timing.beat_zero_offset,
        },
        "data": [],
    }
    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"].append(
            {
                "dif_name": difficulty,
                "level": chart.level,
                "resolution": resolution,
                "notes": [
                    _dump_memon_note_v0(note, resolution)
                    for note in sorted(
                        set(chart.notes), key=lambda n: (n.time, n.position)
                    )
                ],
            }
        )

    if path.is_dir():
        filepath = path / f"{song.metadata.title}.memon"
    else:
        filepath = path

    return {filepath: _dump_to_json(memon)}


def dump_memon_0_1_0(song: jbt.Song, path: Path, **kwargs: dict) -> Dict[Path, bytes]:

    _raise_if_unfit_for_v0(song, "v0.1.0")
    timing = _get_timing(song)

    memon: Dict[str, Any] = {
        "version": "0.1.0",
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "album cover path": str(song.metadata.cover),
            "BPM": timing.events[0].BPM,
            "offset": -timing.beat_zero_offset,
        },
        "data": dict(),
    }
    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"][difficulty] = {
            "level": chart.level,
            "resolution": resolution,
            "notes": [
                _dump_memon_note_v0(note, resolution)
                for note in sorted(set(chart.notes), key=lambda n: (n.time, n.position))
            ],
        }

    if path.is_dir():
        filepath = path / f"{song.metadata.title}.memon"
    else:
        filepath = path

    return {filepath: _dump_to_json(memon)}


def dump_memon_0_2_0(song: jbt.Song, path: Path, **kwargs: dict) -> Dict[Path, bytes]:

    _raise_if_unfit_for_v0(song, "v0.2.0")
    timing = _get_timing(song)

    memon: Dict[str, Any] = {
        "version": "0.2.0",
        "metadata": {
            "song title": song.metadata.title,
            "artist": song.metadata.artist,
            "music path": str(song.metadata.audio),
            "album cover path": str(song.metadata.cover),
            "BPM": timing.events[0].BPM,
            "offset": -timing.beat_zero_offset,
        },
        "data": {},
    }

    if song.metadata.preview is not None:
        memon["metadata"]["preview"] = {
            "position": song.metadata.preview.start,
            "length": song.metadata.preview.length,
        }

    for difficulty, chart in song.charts.items():
        resolution = _compute_resolution(chart.notes)
        memon["data"][difficulty] = {
            "level": chart.level,
            "resolution": resolution,
            "notes": [
                _dump_memon_note_v0(note, resolution)
                for note in sorted(set(chart.notes), key=lambda n: (n.time, n.position))
            ],
        }

    if path.is_dir():
        filepath = path / f"{song.metadata.title}.memon"
    else:
        filepath = path

    return {filepath: _dump_to_json(memon)}
