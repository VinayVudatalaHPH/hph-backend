from marshmallow import Schema, fields

from app.extensions import db
from app.features.models import Feature
from app.responses import envelope_schema
from app.roles.models import role_features


class LoginSchema(Schema):
    email = fields.String(required=True)
    password = fields.String(required=True)


class RoleProfileSchema(Schema):
    id = fields.Integer()
    title = fields.String()
    role_type = fields.Method("get_role_type", data_key="roleType")
    session_timeout_minutes = fields.Method(
        "get_session_timeout_minutes", data_key="sessionTimeoutMinutes"
    )
    features = fields.Method("get_features")
    feature_permissions = fields.Method("get_feature_permissions", data_key="featurePermissions")

    def get_role_type(self, role):
        return role.role_type.code

    def get_session_timeout_minutes(self, role):
        return role.role_type.session_timeout_minutes

    def get_features(self, role):
        # inactive features are treated as absent, same as require_feature()
        return sorted(
            permission["codename"]
            for permission in self._permissions(role)
            if permission["canRead"] or permission["canWrite"]
        )

    def get_feature_permissions(self, role):
        return self._permissions(role)

    @staticmethod
    def _permissions(role):
        rows = db.session.execute(
            db.select(
                Feature.codename,
                role_features.c.can_read,
                role_features.c.can_write,
            )
            .select_from(role_features.join(Feature, Feature.id == role_features.c.feature_id))
            .where(role_features.c.role_id == role.id, Feature.active.is_(True))
            .order_by(Feature.codename)
        ).all()
        return [
            {
                "codename": row.codename,
                "canRead": row.can_read,
                "canWrite": row.can_write,
            }
            for row in rows
        ]


class UserProfileSchema(Schema):
    id = fields.Integer()
    email = fields.Email()
    first_name = fields.String(data_key="firstName")
    last_name = fields.String(data_key="lastName")
    emp_id = fields.String(data_key="empId")
    first_login = fields.Boolean(data_key="firstLogin")
    is_active = fields.Boolean(data_key="isActive")
    project = fields.Method("get_project")
    role = fields.Method("get_role")

    def get_project(self, user):
        return user.project.name if user.project else None

    def get_role(self, user):
        return RoleProfileSchema().dump(user.role)


class LoginDataSchema(Schema):
    user = fields.Nested(UserProfileSchema)


class SessionSchema(Schema):
    id = fields.Integer()
    created_at = fields.DateTime(data_key="createdAt")
    last_seen_at = fields.DateTime(data_key="lastSeenAt")
    expires_at = fields.DateTime(data_key="expiresAt")
    ip_address = fields.String(data_key="ipAddress", allow_none=True)
    user_agent = fields.String(data_key="userAgent", allow_none=True)
    is_current = fields.Boolean(data_key="isCurrent")


LoginEnvelopeSchema = envelope_schema("LoginEnvelopeSchema", fields.Nested(LoginDataSchema))
SessionListEnvelopeSchema = envelope_schema(
    "SessionListEnvelopeSchema", fields.List(fields.Nested(SessionSchema))
)
