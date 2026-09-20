from flask_smorest import Blueprint

bp = Blueprint(
    "login_hours",
    __name__,
    url_prefix="/api",
    description="Manager-uploaded office login-hour records.",
)

from app.login_hours import routes  # noqa: E402,F401
