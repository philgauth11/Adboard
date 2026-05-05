from datetime import date, timedelta
from flask import Blueprint, render_template, request, abort
from flask_login import current_user
from decorators import require_role
from sqlalchemy import func
from models import Client, AdMetric, SyncLog
from extensions import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

RANGE_OPTIONS = [
    ("today",     "Aujourd'hui"),
    ("yesterday", "Hier"),
    ("7d",        "7 derniers jours"),
    ("30d",       "30 derniers jours"),
    ("90d",       "90 derniers jours"),
    ("this_year", "Cette année"),
    ("ytd",       "Cumul annuel"),
    ("custom",    "Personnaliser"),
]

def _date_range(range_str, custom_start=None, custom_end=None):
    today = date.today()
    if range_str == "today":
        return today, today
    if range_str == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if range_str == "7d":
        return today - timedelta(days=7), today
    if range_str == "90d":
        return today - timedelta(days=90), today
    if range_str in ("this_year", "ytd"):
        return date(today.year, 1, 1), today
    if range_str == "custom":
        try:
            return date.fromisoformat(custom_start), date.fromisoformat(custom_end)
        except (ValueError, TypeError):
            return today - timedelta(days=30), today
    return today - timedelta(days=30), today  # default: 30d

def _roas_class(roas):
    if roas >= 4:  return "roas-good"
    if roas >= 2:  return "roas-ok"
    return "roas-bad"

def _aggregate_metrics(client_id, level, start, end):
    base_agg = [
        func.sum(AdMetric.spend).label("spend"),
        func.sum(AdMetric.revenue).label("revenue"),
        func.sum(AdMetric.clicks).label("clicks"),
        func.sum(AdMetric.impressions).label("impressions"),
        func.sum(AdMetric.purchases).label("purchases"),
        func.sum(AdMetric.reach).label("reach"),
    ]
    base_filter = [
        AdMetric.client_id == client_id,
        AdMetric.level == level,
        AdMetric.date >= start,
        AdMetric.date <= end,
    ]

    if level == "campaign":
        cols = [AdMetric.campaign_id, AdMetric.campaign_name, AdMetric.platform]
    elif level == "adset":
        cols = [AdMetric.adset_id, AdMetric.adset_name,
                AdMetric.campaign_name, AdMetric.platform]
    else:  # ad
        cols = [AdMetric.ad_id, AdMetric.ad_name,
                AdMetric.adset_name, AdMetric.campaign_name, AdMetric.platform]

    rows = (db.session.query(*cols, *base_agg)
            .filter(*base_filter)
            .group_by(*cols)
            .order_by(func.sum(AdMetric.spend).desc())
            .all())

    result = []
    for r in rows:
        spend       = float(r.spend or 0)
        revenue     = float(r.revenue or 0)
        clicks      = int(r.clicks or 0)
        impressions = int(r.impressions or 0)
        purchases   = int(r.purchases or 0)
        base = {
            "campaign_id": None, "campaign_name": None,
            "adset_id": None,    "adset_name": None,
            "ad_id": None,       "ad_name": None,
            "platform": r.platform,
            "spend": spend, "revenue": revenue, "clicks": clicks,
            "impressions": impressions, "purchases": purchases,
            "ctr":  round(clicks / impressions * 100, 2) if impressions else 0,
            "cpc":  round(spend / clicks, 2) if clicks else 0,
            "cpm":  round(spend / impressions * 1000, 2) if impressions else 0,
            "roas": round(revenue / spend, 2) if spend else 0,
        }
        if level == "campaign":
            base.update({"campaign_id": r.campaign_id, "campaign_name": r.campaign_name})
        elif level == "adset":
            base.update({"adset_id": r.adset_id, "adset_name": r.adset_name,
                         "campaign_name": r.campaign_name})
        else:
            base.update({"ad_id": r.ad_id, "ad_name": r.ad_name,
                         "adset_name": r.adset_name, "campaign_name": r.campaign_name})
        result.append(base)
    return result

@admin_bp.route("/")
@require_role("superadmin", "admin", "user")
def dashboard():
    range_str = request.args.get("range", "30d")
    platform  = request.args.get("platform", "all")
    custom_start = request.args.get("start", "")
    custom_end   = request.args.get("end", "")
    start, end = _date_range(range_str, custom_start, custom_end)

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
        .filter(AdMetric.date >= start, AdMetric.date <= end, AdMetric.level == "campaign")
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
        client_data=client_data, range=range_str, platform=platform,
        range_options=RANGE_OPTIONS, custom_start=custom_start, custom_end=custom_end,
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
    range_str    = request.args.get("range", "30d")
    custom_start = request.args.get("start", "")
    custom_end   = request.args.get("end", "")
    view         = request.args.get("view", "campaign")
    if view not in ("campaign", "adset", "ad"):
        view = "campaign"
    start, end = _date_range(range_str, custom_start, custom_end)

    level = view  # campaign | adset | ad
    rows = _aggregate_metrics(c.id, level, start, end)
    sync_history = SyncLog.query.filter_by(client_id=c.id).order_by(SyncLog.ran_at.desc()).limit(20).all()

    spend   = sum(r["spend"]   for r in rows)
    revenue = sum(r["revenue"] for r in rows)
    clicks  = sum(r["clicks"]  for r in rows)
    roas    = round(revenue / spend, 2) if spend else 0

    return render_template("admin/client_detail.html",
        c=c, rows=rows, sync_history=sync_history,
        range=range_str, range_options=RANGE_OPTIONS,
        custom_start=custom_start, custom_end=custom_end,
        view=view,
        spend=spend, revenue=revenue, clicks=clicks, roas=roas,
        roas_class=_roas_class(roas),
    )
