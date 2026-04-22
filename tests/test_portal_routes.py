import bcrypt
from datetime import date
from models import Client, AdMetric, ClientUser
from extensions import db

def _seed(db):
    c = Client(name="Boutique Lux", slug="boutique-lux", meta_account_id="act_1")
    db.session.add(c); db.session.commit()
    db.session.add(AdMetric(
        client_id=c.id, platform="meta", level="campaign", date=date(2026,4,15),
        campaign_id="1", campaign_name="Spring", spend=100.0, revenue=500.0, roas=5.0,
    ))
    db.session.commit()
    return c

def test_portal_accessible_via_secret_token(client, db):
    c = _seed(db)
    r = client.get(f"/client/{c.secret_token}")
    assert r.status_code == 200
    assert b"Boutique Lux" in r.data

def test_portal_returns_404_for_invalid_token(client, db):
    r = client.get("/client/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404

def test_portal_login_with_valid_client_account(client, db):
    c = _seed(db)
    pw = bcrypt.hashpw(b"pw123", bcrypt.gensalt()).decode()
    u = ClientUser(client_id=c.id, email="client@lux.com", password_hash=pw)
    db.session.add(u); db.session.commit()
    r = client.post("/client/login",
        data={"email": "client@lux.com", "password": "pw123"},
        follow_redirects=True)
    assert r.status_code == 200
    assert b"Boutique Lux" in r.data

def test_portal_login_rejects_wrong_password(client, db):
    c = _seed(db)
    pw = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode()
    u = ClientUser(client_id=c.id, email="client@lux.com", password_hash=pw)
    db.session.add(u); db.session.commit()
    r = client.post("/client/login", data={"email": "client@lux.com", "password": "wrong"})
    assert r.status_code == 200
    assert b"incorrect" in r.data.lower()
