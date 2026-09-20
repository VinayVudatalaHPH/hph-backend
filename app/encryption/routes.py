import base64

from flask.views import MethodView

from app.encryption import bp
from app.encryption.schemas import CurrentKeyEnvelopeSchema
from app.encryption.services import get_active_key


@bp.route("/encryption/current-key")
class CurrentKey(MethodView):
    @bp.response(200, CurrentKeyEnvelopeSchema)
    def get(self):
        # Deliberately unauthenticated (see app/sessions/hooks.py's
        # EXEMPT_PATHS) — a brand-new client needs this key before it can
        # log in at all, since login itself is now encrypted like every
        # other endpoint. TLS-only in any real deployment. This is the one
        # exception to "encrypt everything," since it can't encrypt the
        # very key a client needs to decrypt everything else. The key
        # itself is shared by every logged-in user regardless, so this
        # isn't a new secret being exposed — TLS is what actually protects
        # it in transit.
        key_version, raw_key = get_active_key()
        return {
            "status": 200,
            "message": "Current encryption key retrieved successfully.",
            "data": {"key_version": key_version, "key": base64.b64encode(raw_key).decode()},
        }
