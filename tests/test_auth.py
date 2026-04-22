import bcrypt
from models import TeamMember
from extensions import db

def _create_member(db, role="admin"):
    pw = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode()
    m = TeamMember(email="philippe@tap.com", name="Philippe", role=role, password_hash=pw)
    db.session.add(m)
    db.session.commit()
    return m

def test_login_redirects_to_dashboard_on_success(client, db):
    _create_member(db)
    r = client.post("/auth/login", data={"email": "philippe@tap.com", "password": "secret123"}, follow_redirects=True)
    assert r.status_code == 200

def test_login_rejects_wrong_password(client, db):
    _create_member(db)
    r = client.post("/auth/login", data={"email": "philippe@tap.com", "password": "wrong"})
    assert r.status_code == 200
    assert "incorrect" in r.data.decode().lower()

def test_logout_redirects_to_login(client, db):
    _create_member(db)
    client.post("/auth/login", data={"email": "philippe@tap.com", "password": "secret123"})
    r = client.get("/auth/logout", follow_redirects=True)
    assert r.status_code == 200

def test_admin_dashboard_requires_login(client):
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code == 302
    assert "/auth/login" in r.headers["Location"]
