from functools import wraps

from flask import g, request
from flask_smorest import abort

from app.extensions import db


def _forbidden(message):
    abort(403, message=message)


def has_role(user, role_type_code):
    return user is not None and user.role.role_type.code == role_type_code


def has_feature(user, codename, access="read"):
    # Import lazily: app.roles registers routes that import these decorators,
    # so importing its models while this module initializes creates a cycle.
    from app.roles.models import role_features

    if user is None:
        return False

    feature = next(
        (feature for feature in user.role.features if feature.codename == codename and feature.active),
        None,
    )
    if feature is None:
        return False

    permission = db.session.execute(
        db.select(role_features.c.can_read, role_features.c.can_write).where(
            role_features.c.role_id == user.role_id,
            role_features.c.feature_id == feature.id,
        )
    ).one_or_none()
    if permission is None:
        return False
    if access == "write":
        return bool(permission.can_write)
    return bool(permission.can_read or permission.can_write)


def require_role(role_type_code):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not has_role(getattr(g, "user", None), role_type_code):
                return _forbidden(f"This action requires the '{role_type_code}' role type.")
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def require_role_types(*role_type_codes):
    allowed = set(role_type_codes)

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            user = getattr(g, "user", None)
            if user is None or user.role.role_type.code not in allowed:
                return _forbidden(
                    f"This action requires one of these role types: {', '.join(sorted(allowed))}."
                )
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def require_feature(codename, access=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            required_access = access or ("read" if request.method in {"GET", "HEAD", "OPTIONS"} else "write")
            if not has_feature(getattr(g, "user", None), codename, required_access):
                return _forbidden(
                    f"This action requires {required_access} access to the '{codename}' feature."
                )
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
