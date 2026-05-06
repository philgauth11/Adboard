import bcrypt
from datetime import date
from models import TeamMember, Client, AdMetric
from extensions import db


def _login_admin(client_fixture, db):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="admin@tap.com", name="A", role="admin", password_hash=pw)
    db.session.add(m); db.session.commit()
    client_fixture.post("/auth/login", data={"email": "admin@tap.com", "password": "pw"})


def _seed(db):
    c = Client(name="X", slug="x", meta_account_id="act_1")
    db.session.add(c); db.session.commit()
    for d, spend in [(date(2026, 4, 14), 40.0), (date(2026, 4, 15), 60.0)]:
        db.session.add(AdMetric(
            client_id=c.id, platform="meta", level="campaign", date=d,
            campaign_id="1", campaign_name="C", spend=spend, revenue=spend*5, roas=5.0,
        ))
    db.session.commit()
    return c


def test_chart_endpoint_returns_labels_and_series(client, db):
    _login_admin(client, db)
    c = _seed(db)
    r = client.get(f"/api/marque/{c.id}/chart?range=30d")
    assert r.status_code == 200
    data = r.get_json()
    assert "labels" in data
    assert "meta" in data
    assert "google" in data
    assert len(data["labels"]) == len(data["meta"])


def test_chart_endpoint_requires_login(client, db):
    c = _seed(db)
    r = client.get(f"/api/marque/{c.id}/chart?range=30d")
    assert r.status_code in (302, 401)
