import bcrypt
from datetime import date
from models import TeamMember, Client, AdMetric
from extensions import db

def _login_admin(client_fixture, db):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="admin@tap.com", name="Admin", role="superadmin", password_hash=pw)
    db.session.add(m)
    db.session.commit()
    client_fixture.post("/auth/login", data={"email": "admin@tap.com", "password": "pw"})

def _seed_client_with_metrics(db, name="Boutique Lux", slug="boutique-lux"):
    c = Client(name=name, slug=slug, meta_account_id="act_123")
    db.session.add(c)
    db.session.commit()
    m = AdMetric(
        client_id=c.id, platform="meta", level="campaign",
        date=date(2026, 4, 15), campaign_id="1", campaign_name="Spring",
        impressions=10000, clicks=200, spend=100.0, revenue=500.0, roas=5.0,
    )
    db.session.add(m)
    db.session.commit()
    return c

def test_dashboard_requires_login(client):
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code == 302

def test_dashboard_returns_200_when_logged_in(client, db):
    _login_admin(client, db)
    r = client.get("/admin/")
    assert r.status_code == 200

def test_dashboard_shows_client_name(client, db):
    _login_admin(client, db)
    _seed_client_with_metrics(db)
    r = client.get("/admin/")
    assert b"Boutique Lux" in r.data

def test_client_detail_returns_200(client, db):
    _login_admin(client, db)
    c = _seed_client_with_metrics(db)
    r = client.get(f"/admin/client/{c.id}")
    assert r.status_code == 200

def test_client_detail_403_for_unauthorized_user(client, db):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="user@tap.com", name="U", role="user", password_hash=pw)
    db.session.add(m)
    db.session.commit()
    c = _seed_client_with_metrics(db)
    client.post("/auth/login", data={"email": "user@tap.com", "password": "pw"})
    r = client.get(f"/admin/client/{c.id}")
    assert r.status_code == 403
