from marshmallow import Schema, fields, validate

from app.responses import envelope_schema


class FeatureSchema(Schema):
    id = fields.Integer(dump_only=True)
    codename = fields.String(required=True, validate=validate.Length(min=1, max=64))
    title = fields.String(required=True, validate=validate.Length(min=1, max=128))
    description = fields.String(allow_none=True, load_default=None)
    active = fields.Boolean(load_default=True)


class AssignFeatureSchema(Schema):
    feature_id = fields.Integer(required=True)
    can_read = fields.Boolean(load_default=True)
    can_write = fields.Boolean(load_default=False)


FeatureEnvelopeSchema = envelope_schema("FeatureEnvelopeSchema", fields.Nested(FeatureSchema))
FeatureListEnvelopeSchema = envelope_schema(
    "FeatureListEnvelopeSchema", fields.List(fields.Nested(FeatureSchema))
)
