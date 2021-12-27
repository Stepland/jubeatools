from typing import Any, Dict

from marshmallow import (
    RAISE,
    Schema,
    ValidationError,
    fields,
    validate,
    validates_schema,
)

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
        ordered = True
        unknown = RAISE


class MemonNote(StrictSchema):
    n = fields.Integer(required=True, validate=validate.Range(min=0, max=15))
    t = fields.Integer(required=True, validate=validate.Range(min=0))
    # flake8 doesn't like "l" as a name here, so I silence the precise warning
    l = fields.Integer(required=True, validate=validate.Range(min=0))  # noqa: E741
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


class MemonMetadata_0_3_0(MemonMetadata_0_2_0):
    audio = fields.String(required=False, data_key="music path")
    cover = fields.String(required=False, data_key="album cover path")
    preview_path = fields.String(data_key="preview path")


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


class Memon_0_3_0(StrictSchema):
    version = fields.String(required=True, validate=validate.OneOf(["0.3.0"]))
    metadata = fields.Nested(MemonMetadata_0_3_0, required=True)
    data = fields.Dict(
        keys=fields.String(), values=fields.Nested(MemonChart_0_1_0), required=True
    )
