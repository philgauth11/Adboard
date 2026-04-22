from flask import Blueprint
from flask_login import login_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/")
@login_required
def dashboard():
    return "Dashboard coming soon", 200
