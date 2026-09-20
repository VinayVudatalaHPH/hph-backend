from flask_smorest import Blueprint

bp = Blueprint("roles", __name__, url_prefix="/api", description="Role and role-type management")

from app.roles import routes  # noqa: E402,F401
