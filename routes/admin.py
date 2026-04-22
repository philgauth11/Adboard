from flask import Blueprint
from decorators import require_role

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/")
@require_role("superadmin", "admin", "user")
def dashboard():
    return "admin dashboard stub", 200
