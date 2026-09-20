from flask_smorest import Blueprint

bp = Blueprint(
    "encryption", __name__, url_prefix="/api", description="Application-level payload encryption key exchange"
)

from app.encryption import routes  # noqa: E402,F401
