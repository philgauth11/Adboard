from flask import Blueprint, render_template_string
from flask_login import login_required
from decorators import require_role

access_bp = Blueprint("access", __name__, url_prefix="/admin/access")

@access_bp.route("/")
@require_role("superadmin", "admin")
def index():
    return render_template_string("<h1>Access management — coming soon</h1>")
