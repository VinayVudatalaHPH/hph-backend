from flask_smorest import Blueprint

bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/api",
    description="Personal Reports view (own Kairon + Manual data) and the Coding project dashboard.",
)

from app.reports import routes  # noqa: E402,F401
