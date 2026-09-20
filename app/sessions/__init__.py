from flask_smorest import Blueprint

bp = Blueprint(
    "sessions", __name__, url_prefix="/api", description="Login, logout, and session listing"
)

from app.sessions import routes  # noqa: E402,F401
