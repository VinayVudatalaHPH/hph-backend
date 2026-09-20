from flask_smorest import Blueprint

bp = Blueprint("cohorts", __name__, url_prefix="/api", description="Coder cohorts, stage progression, and target configuration")

from app.cohorts import routes  # noqa: E402,F401
