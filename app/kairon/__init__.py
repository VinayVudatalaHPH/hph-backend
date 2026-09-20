from flask_smorest import Blueprint

bp = Blueprint(
    "kairon",
    __name__,
    url_prefix="/api",
    description="Kairon chart-review records: bulk upload, coding-analyst resolution, and batch history",
)

from app.kairon import routes  # noqa: E402,F401
