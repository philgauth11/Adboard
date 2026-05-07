import uuid
import bcrypt
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from models import TeamMember, Client, TeamMemberClient
from extensions import db
from decorators import require_role
from mailer import send_invitation

access_bp = Blueprint("access", __name__, url_prefix="/admin/access")


@access_bp.route("/")
@require_role("admin")
def index():
    members = TeamMember.query.order_by(TeamMember.created_at).all()
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()
    client_map = {c.id: c for c in clients}
    member_brands = {
        m.id: {tc.client_id for tc in m.assigned_clients}
        for m in members if m.role == "client"
    }
    from fetchers.meta_fetcher import fetch_ad_accounts
    try:
        meta_accounts = fetch_ad_accounts()
    except Exception:
        meta_accounts = []
    return render_template("admin/access.html",
        members=members, clients=clients, client_map=client_map,
        member_brands=member_brands, current_member=current_user,
        meta_accounts=meta_accounts)


@access_bp.route("/invite", methods=["POST"])
@require_role("admin")
def invite():
    email = request.form.get("email", "").strip().lower()
    name  = request.form.get("name", "").strip()
    role  = request.form.get("role", "admin")
    if role not in ("admin", "client"):
        role = "admin"
    if TeamMember.query.filter_by(email=email).first():
        flash("Cet email est déjà enregistré.")
        return redirect(url_for("access.index"))
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=48)
    m = TeamMember(email=email, name=name, role=role, invite_token=token, invite_expires_at=expires)
    db.session.add(m)
    db.session.flush()
    if role == "client":
        for brand_id in request.form.getlist("brand_ids"):
            try:
                db.session.add(TeamMemberClient(team_member_id=m.id, client_id=int(brand_id)))
            except (ValueError, Exception):
                pass
    db.session.commit()
    invite_url = url_for("access.accept_invite", token=token, _external=True)
    send_invitation(email, name, invite_url)
    flash(f"Invitation envoyée à {email}.")
    return redirect(url_for("access.index"))


@access_bp.route("/accept/<string:token>", methods=["GET", "POST"])
def accept_invite(token):
    m = TeamMember.query.filter_by(invite_token=token).first_or_404()
    if m.invite_expires_at < datetime.utcnow():
        flash("Ce lien d'invitation a expiré.")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        pw = request.form.get("password", "")
        m.password_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        m.invite_token = None
        m.invite_expires_at = None
        db.session.commit()
        flash("Compte créé ! Tu peux te connecter.")
        return redirect(url_for("auth.login"))
    return render_template("auth/accept_invite.html", member=m)


@access_bp.route("/revoke/<int:member_id>", methods=["POST"])
@require_role("admin")
def revoke(member_id):
    m = db.session.get(TeamMember, member_id)
    if m is None:
        abort(404)
    m.password_hash = None
    m.invite_token = None
    db.session.commit()
    flash(f"Accès révoqué pour {m.name}.")
    return redirect(url_for("access.index"))


@access_bp.route("/client/new", methods=["POST"])
@require_role("admin")
def new_client():
    name = request.form.get("name", "").strip()
    meta_id   = request.form.get("meta_account_id", "").strip() or None
    google_id = request.form.get("google_customer_id", "").strip() or None
    slug = name.lower().replace(" ", "-")
    c = Client(name=name, slug=slug, meta_account_id=meta_id, google_customer_id=google_id)
    db.session.add(c); db.session.commit()
    flash(f"Marque '{name}' ajoutée.")
    return redirect(url_for("access.index"))


@access_bp.route("/client/<int:client_id>/deactivate", methods=["POST"])
@require_role("admin")
def deactivate_client(client_id):
    c = db.session.get(Client, client_id)
    if c is None:
        abort(404)
    c.is_active = False
    db.session.commit()
    flash(f"Marque '{c.name}' désactivée.")
    return redirect(url_for("access.index"))


@access_bp.route("/assign-brands/<int:member_id>", methods=["POST"])
@require_role("admin")
def assign_brands(member_id):
    m = db.session.get(TeamMember, member_id)
    if m is None or m.role != "client":
        abort(404)
    TeamMemberClient.query.filter_by(team_member_id=m.id).delete()
    for brand_id in request.form.getlist("brand_ids"):
        try:
            db.session.add(TeamMemberClient(team_member_id=m.id, client_id=int(brand_id)))
        except ValueError:
            pass
    db.session.commit()
    flash(f"Marques mises à jour pour {m.name}.")
    return redirect(url_for("access.index"))
