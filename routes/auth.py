import bcrypt
from datetime import datetime, UTC
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from extensions import db
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


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    from flask_login import current_user
    error = None
    if request.method == "POST":
        current_pw = request.form.get("current_password", "").encode()
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not bcrypt.checkpw(current_pw, current_user.password_hash.encode()):
            error = "Mot de passe actuel incorrect."
        elif len(new_pw) < 8:
            error = "Le nouveau mot de passe doit contenir au moins 8 caractères."
        elif new_pw != confirm:
            error = "Les deux mots de passe ne correspondent pas."
        else:
            current_user.password_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
            db.session.commit()
            flash("Mot de passe modifié avec succès.")
            return redirect(url_for("admin.dashboard"))
    return render_template("auth/change_password.html", error=error)
