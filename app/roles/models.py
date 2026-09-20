from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history

from app.extensions import db
from app.features.models import Feature  # noqa: F401 (needed for the relationship below)

_PROTECTED_FIELDS = ("code", "label", "hierarchy_rank")


class RoleType(db.Model):
    __tablename__ = "role_types"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    label = db.Column(db.String(64), nullable=False)
    hierarchy_rank = db.Column(db.Integer, unique=True, nullable=False)
    session_timeout_minutes = db.Column(db.Integer, nullable=False, default=30)

    def __repr__(self):
        return f"<RoleType {self.code}>"


@event.listens_for(RoleType, "before_update")
def _protect_role_type_identity(mapper, connection, target):
    for field in _PROTECTED_FIELDS:
        if get_history(target, field).has_changes():
            raise ValueError(
                f"RoleType.{field} is fixed seed data and cannot be changed."
            )


@event.listens_for(RoleType, "before_delete")
def _protect_role_type_deletion(mapper, connection, target):
    raise ValueError("RoleType rows are fixed seed data and cannot be deleted.")


role_features = db.Table(
    "role_features",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("feature_id", db.Integer, db.ForeignKey("features.id"), primary_key=True),
    db.Column("can_read", db.Boolean, nullable=False, default=True, server_default=db.true()),
    db.Column("can_write", db.Boolean, nullable=False, default=True, server_default=db.true()),
)


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    role_type_id = db.Column(
        db.Integer, db.ForeignKey("role_types.id", ondelete="RESTRICT"), nullable=False
    )
    title = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    role_type = db.relationship("RoleType")
    features = db.relationship("Feature", secondary=role_features, backref="roles")

    def __repr__(self):
        return f"<Role {self.title}>"
