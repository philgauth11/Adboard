from unittest.mock import patch
from datetime import date
from models import Client, AdMetric, SyncLog
from extensions import db
from sync import sync_client, _upsert_metrics

def _make_client(db, meta_id="act_123", google_id=None):
    c = Client(name="Test", slug="test", meta_account_id=meta_id, google_customer_id=google_id)
    db.session.add(c)
    db.session.commit()
    return c

def _sample_rows():
    return [{
        "date": "2026-04-01", "campaign_id": "1", "campaign_name": "Spring",
        "adset_id": None, "adset_name": None,
        "impressions": 1000, "reach": 800, "frequency": 1.25, "clicks": 50,
        "ctr": 5.0, "cpc": 0.50, "cpm": 5.0, "spend": 25.0,
        "purchases": 3, "revenue": 150.0, "roas": 6.0,
    }]

def test_upsert_metrics_saves_rows(app, db):
    c = _make_client(db)
    _upsert_metrics(c.id, "meta", "campaign", _sample_rows())
    db.session.commit()
    metrics = AdMetric.query.filter_by(client_id=c.id).all()
    assert len(metrics) == 1
    assert metrics[0].roas == 6.0

def test_upsert_metrics_replaces_existing_rows_for_same_date(app, db):
    c = _make_client(db)
    _upsert_metrics(c.id, "meta", "campaign", _sample_rows())
    db.session.commit()
    updated = _sample_rows()
    updated[0]["roas"] = 7.5
    _upsert_metrics(c.id, "meta", "campaign", updated)
    db.session.commit()
    metrics = AdMetric.query.filter_by(client_id=c.id).all()
    assert len(metrics) == 1
    assert metrics[0].roas == 7.5

@patch("sync.fetch_meta_campaigns")
@patch("sync.fetch_meta_adsets")
def test_sync_client_creates_success_log(mock_adsets, mock_campaigns, app, db):
    mock_campaigns.return_value = _sample_rows()
    mock_adsets.return_value = _sample_rows()
    c = _make_client(db)
    sync_client(c)
    logs = SyncLog.query.filter_by(client_id=c.id, status="success").all()
    assert len(logs) >= 1

@patch("sync.fetch_meta_campaigns", side_effect=Exception("API down"))
@patch("sync.fetch_meta_adsets", side_effect=Exception("API down"))
def test_sync_client_logs_error_on_exception(mock_adsets, mock_campaigns, app, db):
    c = _make_client(db)
    sync_client(c)
    logs = SyncLog.query.filter_by(client_id=c.id, status="error").all()
    assert len(logs) >= 1
