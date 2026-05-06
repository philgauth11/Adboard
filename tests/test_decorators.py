import bcrypt
from models import TeamMember
from extensions import db


def _login(client_fixture, db, role="admin"):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email=f"{role}@tap.com", name="Test", role=role, password_hash=pw)
    db.session.add(m)
    db.session.commit()
    client_fixture.post("/auth/login", data={"email": f"{role}@tap.com", "password": "pw"})
    return m


def test_admin_can_access_dashboard(client, db):
    _login(client, db, role="admin")
    r = client.get("/admin/")
    assert r.status_code == 200


def test_client_can_access_dashboard(client, db):
    _login(client, db, role="client")
    r = client.get("/admin/")
    assert r.status_code == 200


def test_unauthenticated_redirected_to_login(client):
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code == 302


def test_client_cannot_access_access_page(client, db):
    _login(client, db, role="client")
    r = client.get("/admin/access/")
    assert r.status_code in (403, 404)
