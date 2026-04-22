import bcrypt
from datetime import date, timedelta, datetime, UTC
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from models import Client, ClientUser, AdMetric, SyncLog
from extensions import db

portal_bp = Blueprint("portal", __name__, url_prefix="/client")

def _period_start(days):
    return date.today() - timedelta(days=days)

def _get_portal_client():
    client_id = session.get("portal_client_id")
    if not client_id:
        return None
    return Client.query.filter_by(id=client_id, is_active=True).first()

@portal_bp.route("/<string:token>")
def portal_by_token(token):
    c = Client.query.filter_by(secret_token=token, is_active=True).first_or_404()
    session["portal_client_id"] = c.id

    days = int(request.args.get("days", 30))
    start = _period_start(days)

    campaigns = (AdMetric.query
        .filter_by(client_id=c.id, level="campaign")
        .filter(AdMetric.date >= start)
        .order_by(AdMetric.spend.desc())
        .all())

    spend   = sum(m.spend for m in campaigns)
    revenue = sum(m.revenue for m in campaigns)
    clicks  = sum(m.clicks for m in campaigns)
    roas    = round(revenue / spend, 2) if spend else 0

    last_sync = (SyncLog.query
        .filter_by(client_id=c.id, status="success")
        .order_by(SyncLog.ran_at.desc())
        .first())

    return render_template("portal/client.html",
        c=c, campaigns=campaigns, days=days,
        spend=spend, revenue=revenue, clicks=clicks, roas=roas,
        last_sync=last_sync,
    )

@portal_bp.route("/dashboard")
def portal_dashboard():
    c = _get_portal_client()
    if not c:
        return redirect(url_for("portal.portal_login"))

    days = int(request.args.get("days", 30))
    start = _period_start(days)

    campaigns = (AdMetric.query
        .filter_by(client_id=c.id, level="campaign")
        .filter(AdMetric.date >= start)
        .order_by(AdMetric.spend.desc())
        .all())

    spend   = sum(m.spend for m in campaigns)
    revenue = sum(m.revenue for m in campaigns)
    clicks  = sum(m.clicks for m in campaigns)
    roas    = round(revenue / spend, 2) if spend else 0

    last_sync = (SyncLog.query
        .filter_by(client_id=c.id, status="success")
        .order_by(SyncLog.ran_at.desc())
        .first())

    return render_template("portal/client.html",
        c=c, campaigns=campaigns, days=days,
        spend=spend, revenue=revenue, clicks=clicks, roas=roas,
        last_sync=last_sync,
    )

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
