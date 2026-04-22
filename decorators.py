from functools import wraps
from flask import abort
from flask_login import current_user, login_required


def require_role(*roles):
    """Restrict route to team members with one of the given roles."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return login_required(wrapped)
    return decorator
