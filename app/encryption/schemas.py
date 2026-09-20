from marshmallow import Schema, fields

from app.responses import envelope_schema


class CurrentKeySchema(Schema):
    key_version = fields.Integer(data_key="keyVersion")
    key = fields.String()  # base64-encoded raw AES-256 key


CurrentKeyEnvelopeSchema = envelope_schema("CurrentKeyEnvelopeSchema", fields.Nested(CurrentKeySchema))
