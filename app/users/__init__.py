from flask_smorest import Blueprint

bp = Blueprint("users", __name__, url_prefix="/api", description="User accounts and credentials")

from app.users import routes  # noqa: E402,F401
