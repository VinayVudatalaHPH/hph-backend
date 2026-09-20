from flask import jsonify
from marshmallow import Schema, fields


def api_response(data=None, message="", status=200, **extra):
    body = {"status": status, "message": message, "data": data}
    body.update(extra)
    response = jsonify(body)
    response.status_code = status
    return response


def envelope_schema(name, data_field):
    """Build a Schema class documenting the {status, message, data} envelope
    every response uses, so flask-smorest/OpenAPI shows the real shape."""
    return type(name, (Schema,), {"status": fields.Integer(), "message": fields.String(), "data": data_field})


# Shared envelope for message-only responses (delete/logout/simple errors) —
# blueprints that need a typed "data" shape define their own via envelope_schema.
MessageEnvelopeSchema = envelope_schema("MessageEnvelopeSchema", fields.Raw(allow_none=True))
