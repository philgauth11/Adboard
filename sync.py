from datetime import datetime, date as date_type, UTC
from extensions import db
from models import Client, AdMetric, SyncLog
from fetchers.meta_fetcher import fetch_campaigns as fetch_meta_campaigns, fetch_adsets as fetch_meta_adsets, fetch_ads as fetch_meta_ads
from fetchers.google_fetcher import fetch_campaigns as fetch_google_campaigns, fetch_adsets as fetch_google_adsets, fetch_ads as fetch_google_ads


def _upsert_metrics(client_id, platform, level, rows):
    if not rows:
        return

    def _parse_date(d):
        if isinstance(d, date_type):
            return d
        return datetime.strptime(d, "%Y-%m-%d").date()

    dates = list({_parse_date(r["date"]) for r in rows})
    AdMetric.query.filter(
        AdMetric.client_id == client_id,
        AdMetric.platform == platform,
        AdMetric.level == level,
        AdMetric.date.in_(dates),
    ).delete(synchronize_session=False)
    for r in rows:
        db.session.add(AdMetric(
            client_id=client_id, platform=platform, level=level,
            date=_parse_date(r["date"]),
            campaign_id=r.get("campaign_id"), campaign_name=r.get("campaign_name"),
            adset_id=r.get("adset_id"), adset_name=r.get("adset_name"),
            ad_id=r.get("ad_id"), ad_name=r.get("ad_name"),
            impressions=r.get("impressions", 0), reach=r.get("reach", 0),
            frequency=r.get("frequency", 0.0), clicks=r.get("clicks", 0),
            ctr=r.get("ctr", 0.0), cpc=r.get("cpc", 0.0), cpm=r.get("cpm", 0.0),
            spend=r.get("spend", 0.0), purchases=r.get("purchases", 0),
            revenue=r.get("revenue", 0.0), roas=r.get("roas", 0.0),
            synced_at=datetime.utcnow(),
        ))


def sync_client(client):
    """Sync Meta + Google data for one client. Safe to call from scheduler or manually."""
    jobs = []
    if client.meta_account_id:
        jobs += [
            ("meta", "campaign", fetch_meta_campaigns, {"account_id": client.meta_account_id}),
            ("meta", "adset",    fetch_meta_adsets,    {"account_id": client.meta_account_id}),
            ("meta", "ad",       fetch_meta_ads,       {"account_id": client.meta_account_id}),
        ]
    if client.google_customer_id:
        jobs += [
            ("google", "campaign", fetch_google_campaigns, {"customer_id": client.google_customer_id}),
            ("google", "adset",    fetch_google_adsets,    {"customer_id": client.google_customer_id}),
            ("google", "ad",       fetch_google_ads,       {"customer_id": client.google_customer_id}),
        ]

    errors = []
    for platform, level, fetcher, kwargs in jobs:
        try:
            rows = fetcher(**kwargs)
            _upsert_metrics(client.id, platform, level, rows)
            db.session.add(SyncLog(
                client_id=client.id, platform=platform,
                status="success", rows_fetched=len(rows),
            ))
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            error_msg = str(exc)
            errors.append(f"{platform}/{level}: {error_msg}")
            db.session.add(SyncLog(
                client_id=client.id, platform=platform,
                status="error", error_message=error_msg,
            ))
            db.session.commit()
    return errors


def sync_all_clients(app):
    """APScheduler job — runs every hour."""
    with app.app_context():
        for client in Client.query.filter_by(is_active=True).all():
            sync_client(client)


def init_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(sync_all_clients, "interval", hours=1, args=[app], id="hourly_sync")
    scheduler.start()
    return scheduler
