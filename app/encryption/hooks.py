import io

from cryptography.exceptions import InvalidTag
from flask import current_app, request
from flask_smorest import abort

from app.encryption.crypto import decrypt_payload, encrypt_payload
from app.encryption.services import get_active_key, get_key_for_decryption

KEY_VERSION_HEADER = "X-Encryption-Key-Version"

# The one deliberate exception to "encrypt everything" (§4b): key exchange
# can't encrypt the very key a client needs to decrypt everything else.
# It's also reachable pre-login (see app/sessions/hooks.py's EXEMPT_PATHS)
# specifically so a brand-new client can fetch that key and encrypt its
# very first request — meaning login itself is NOT exempt here; it's
# encrypted like everything else.
ENCRYPTION_EXEMPT_PATHS = {
    ("/api/encryption/current-key", "GET"),
}


def _is_exempt():
    if not request.path.startswith("/api/"):
        return True
    return (request.path, request.method) in ENCRYPTION_EXEMPT_PATHS


def _log_decrypted_payload(direction, key_version, plaintext_bytes, status_code=None):
    """Logs a request/response body decrypted (its plaintext JSON) - i.e.
    the opposite side of the wire from what's actually transmitted: the
    body decrypt_request_body() just produced, or the body
    encrypt_response_body() is about to encrypt. Gated behind
    Config.LOG_DECRYPTED_PAYLOADS (see its docstring): this includes
    request bodies verbatim, so it WILL print things like login passwords
    - local dev only, never enable in production.
    """
    if not current_app.config["LOG_DECRYPTED_PAYLOADS"]:
        return
    status_part = f" status={status_code}" if status_code is not None else ""
    current_app.logger.info(
        "[decrypted %s] %s %s keyVersion=%s bytes=%d%s body=%s",
        direction,
        request.method,
        request.path,
        key_version,
        len(plaintext_bytes),
        status_part,
        plaintext_bytes.decode("utf-8", errors="replace"),
    )


def decrypt_request_body():
    """Runs before load_session (see create_app) so the body is already
    plaintext by the time the session hook, and every view, reads it.
    """
    if _is_exempt() or request.method == "OPTIONS":
        return None

    content_length = request.environ.get("CONTENT_LENGTH")
    if not content_length or int(content_length) <= 0:
        return None  # nothing to decrypt

    version_header = request.headers.get(KEY_VERSION_HEADER)
    if version_header is None:
        abort(400, message=f"Missing {KEY_VERSION_HEADER} header.")
    try:
        key_version = int(version_header)
    except ValueError:
        abort(400, message=f"{KEY_VERSION_HEADER} must be an integer.")

    key = get_key_for_decryption(key_version)
    if key is None:
        abort(400, message="Unknown or expired encryption key version.")

    # Read the raw (still-encrypted) body straight from the WSGI stream —
    # bypassing Werkzeug's own get_data()/get_json(), which would otherwise
    # cache these encrypted bytes as "the" request body before we get a
    # chance to replace them.
    raw_encrypted = request.environ["wsgi.input"].read(int(content_length))
    try:
        decrypted = decrypt_payload(raw_encrypted, key)
    except InvalidTag:
        abort(400, message="Unable to decrypt request body.")
    _log_decrypted_payload("request", key_version, decrypted)

    request.environ["wsgi.input"] = io.BytesIO(decrypted)
    request.environ["CONTENT_LENGTH"] = str(len(decrypted))
    return None


def encrypt_response_body(response):
    """Last step before the response is sent — every JSON body gets
    encrypted with the currently active key, and the response is tagged
    with the key version used so a mid-rotation client always knows which
    key to decrypt with.
    """
    if _is_exempt():
        return response
    if not response.mimetype or "json" not in response.mimetype:
        return response

    key_version, key = get_active_key()
    plaintext = response.get_data()
    _log_decrypted_payload("response", key_version, plaintext, status_code=response.status_code)
    response.set_data(encrypt_payload(plaintext, key))
    response.headers[KEY_VERSION_HEADER] = str(key_version)
    response.mimetype = "application/octet-stream"
    return response
