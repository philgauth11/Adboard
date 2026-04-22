from datetime import date, timedelta
from flask import Blueprint, render_template, request, abort
from flask_login import current_user
from decorators import require_role
from sqlalchemy import func
from models import Client, AdMetric, SyncLog
from extensions import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def _period_start(days):
    return date.today() - timedelta(days=days)

def _roas_class(roas):
    if roas >= 4:  return "roas-good"
    if roas >= 2:  return "roas-ok"
    return "roas-bad"

@admin_bp.route("/")
@require_role("superadmin", "admin", "user")
def dashboard():
    days = int(request.args.get("days", 30))
    platform = request.args.get("platform", "all")
    start = _period_start(days)

    clients = Client.query.filter_by(is_active=True).all()
    if current_user.role == "user":
        allowed = {tc.client_id for tc in current_user.assigned_clients}
        clients = [c for c in clients if c.id in allowed]

    q = (db.session.query(
            AdMetric.client_id,
            func.sum(AdMetric.spend).label("spend"),
            func.sum(AdMetric.revenue).label("revenue"),
            func.sum(AdMetric.clicks).label("clicks"),
            func.sum(AdMetric.purchases).label("purchases"),
        )
        .filter(AdMetric.date >= start, AdMetric.level == "campaign")
    )
    if platform != "all":
        q = q.filter(AdMetric.platform == platform)
    rows = {r.client_id: r for r in q.group_by(AdMetric.client_id).all()}

    last_sync = {
        s.client_id: s.ran_at
        for s in db.session.query(
            SyncLog.client_id,
            func.max(SyncLog.ran_at).label("ran_at")
        ).group_by(SyncLog.client_id).all()
    }

    client_data = []
    for c in clients:
        r = rows.get(c.id)
        spend = float(r.spend or 0) if r else 0
        revenue = float(r.revenue or 0) if r else 0
        clicks = int(r.clicks or 0) if r else 0
        roas = round(revenue / spend, 2) if spend else 0
        client_data.append({
            "client": c,
            "spend": spend,
            "revenue": revenue,
            "clicks": clicks,
            "roas": roas,
            "roas_class": _roas_class(roas),
            "last_sync": last_sync.get(c.id),
        })

    client_data.sort(key=lambda x: x["spend"], reverse=True)

    global_spend   = sum(x["spend"] for x in client_data)
    global_revenue = sum(x["revenue"] for x in client_data)
    global_clicks  = sum(x["clicks"] for x in client_data)
    global_roas    = round(global_revenue / global_spend, 2) if global_spend else 0

    return render_template("admin/dashboard.html",
        client_data=client_data, days=days, platform=platform,
        global_spend=global_spend, global_revenue=global_revenue,
        global_clicks=global_clicks, global_roas=global_roas,
        active_count=len(clients),
    )

@admin_bp.route("/client/<int:client_id>")
@require_role("superadmin", "admin", "user")
def client_detail(client_id):
    if not current_user.can_see_client(client_id):
        abort(403)
    c = db.session.get(Client, client_id)
    if c is None:
        abort(404)
    days = int(request.args.get("days", 30))
    start = _period_start(days)

    campaigns = (AdMetric.query
        .filter_by(client_id=c.id, level="campaign")
        .filter(AdMetric.date >= start)
        .order_by(AdMetric.spend.desc())
        .all()
    )
    sync_history = SyncLog.query.filter_by(client_id=c.id).order_by(SyncLog.ran_at.desc()).limit(20).all()

    spend  = sum(m.spend for m in campaigns)
    revenue= sum(m.revenue for m in campaigns)
    clicks = sum(m.clicks for m in campaigns)
    roas   = round(revenue / spend, 2) if spend else 0

    return render_template("admin/client_detail.html",
        c=c, campaigns=campaigns, sync_history=sync_history, days=days,
        spend=spend, revenue=revenue, clicks=clicks, roas=roas,
        roas_class=_roas_class(roas),
    )
