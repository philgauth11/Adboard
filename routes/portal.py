import bcrypt
from datetime import datetime, UTC
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from models import Client, ClientUser, SyncLog
from extensions import db
from routes.admin import RANGE_OPTIONS, _date_range, _aggregate_metrics

portal_bp = Blueprint("portal", __name__, url_prefix="/client")

def _get_portal_client():
    client_id = session.get("portal_client_id")
    if not client_id:
        return None
    return Client.query.filter_by(id=client_id, is_active=True).first()

def _portal_context(c):
    range_str    = request.args.get("range", "30d")
    custom_start = request.args.get("start", "")
    custom_end   = request.args.get("end", "")
    view         = request.args.get("view", "campaign")
    if view not in ("campaign", "adset", "ad"):
        view = "campaign"
    start, end = _date_range(range_str, custom_start, custom_end)

    level = view  # campaign | adset | ad
    rows = _aggregate_metrics(c.id, level, start, end)

    spend   = sum(r["spend"]   for r in rows)
    revenue = sum(r["revenue"] for r in rows)
    clicks  = sum(r["clicks"]  for r in rows)
    roas    = round(revenue / spend, 2) if spend else 0

    last_sync = (SyncLog.query
        .filter_by(client_id=c.id, status="success")
        .order_by(SyncLog.ran_at.desc())
        .first())

    return dict(
        c=c, rows=rows, view=view,
        range=range_str, range_options=RANGE_OPTIONS,
        custom_start=custom_start, custom_end=custom_end,
        spend=spend, revenue=revenue, clicks=clicks, roas=roas,
        last_sync=last_sync,
    )

@portal_bp.route("/<string:token>")
def portal_by_token(token):
    c = Client.query.filter_by(secret_token=token, is_active=True).first_or_404()
    session["portal_client_id"] = c.id
    return render_template("portal/client.html", **_portal_context(c))

@portal_bp.route("/dashboard")
def portal_dashboard():
    c = _get_portal_client()
    if not c:
        return redirect(url_for("portal.portal_login"))
    return render_template("portal/client.html", **_portal_context(c))

@portal_bp.route("/login", methods=["GET", "POST"])
def portal_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").encode()
        u = ClientUser.query.filter_by(email=email).first()
        if u and u.password_hash and bcrypt.checkpw(password, u.password_hash.encode()):
            session["portal_client_id"] = u.client_id
            u.last_login_at = datetime.now(UTC)
            db.session.commit()
            return redirect(url_for("portal.portal_dashboard"))
        flash("Email ou mot de passe incorrect.")
    return render_template("portal/login.html")
