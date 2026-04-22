import bcrypt
from datetime import datetime, UTC
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from models import TeamMember

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").encode()
        member = TeamMember.query.filter_by(email=email).first()
        if member and member.password_hash and bcrypt.checkpw(password, member.password_hash.encode()):
            login_user(member)
            from extensions import db
            member.last_login_at = datetime.now(UTC)
            db.session.commit()
            return redirect(url_for("admin.dashboard"))
        flash("Email ou mot de passe incorrect.", "error")
    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
