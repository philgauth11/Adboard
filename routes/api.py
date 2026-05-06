from datetime import date, timedelta
from collections import defaultdict
from flask import Blueprint, jsonify, request, abort, current_app
from flask_login import login_required, current_user
from models import Client, AdMetric
from extensions import db
from sqlalchemy import func
import threading

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/marque/<int:client_id>/chart")
@login_required
def client_chart(client_id):
    if not current_user.can_see_client(client_id):
        abort(403)
    from routes.admin import _date_range
    range_str = request.args.get("range", "30d")
    start, end = _date_range(range_str, request.args.get("start"), request.args.get("end"))

    rows = (db.session.query(AdMetric.date, AdMetric.platform, func.sum(AdMetric.spend))
        .filter(AdMetric.client_id == client_id, AdMetric.level == "campaign",
                AdMetric.date >= start, AdMetric.date <= end)
        .group_by(AdMetric.date, AdMetric.platform)
        .order_by(AdMetric.date)
        .all())

    by_date = defaultdict(lambda: {"meta": 0.0, "google": 0.0})
    for row_date, platform, spend in rows:
        by_date[str(row_date)][platform] = round(float(spend), 2)

    labels = sorted(by_date.keys())
    return jsonify({
        "labels": labels,
        "meta":   [by_date[d]["meta"]   for d in labels],
        "google": [by_date[d]["google"] for d in labels],
    })


@api_bp.route("/sync/<int:client_id>", methods=["POST"])
@login_required
def manual_sync(client_id):
    if not current_user.can_see_client(client_id):
        abort(403)
    c = db.session.get(Client, client_id)
    if c is None:
        abort(404)
    from sync import sync_client
    errors = sync_client(c)
    if errors:
        return jsonify({"status": "error", "errors": errors}), 200
    return jsonify({"status": "ok"})


@api_bp.route("/sync/all", methods=["POST"])
@login_required
def manual_sync_all():
    if current_user.role != "admin":
        abort(403)
    from sync import sync_all_clients
    app = current_app._get_current_object()
    t = threading.Thread(target=sync_all_clients, args=[app])
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})
