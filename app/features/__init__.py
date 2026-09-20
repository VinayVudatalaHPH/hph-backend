from flask_smorest import Blueprint

bp = Blueprint("features", __name__, url_prefix="/api", description="Feature management")

from app.features import routes  # noqa: E402,F401
