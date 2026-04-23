import bcrypt
from models import TeamMember, Client, ClientUser
from extensions import db
from unittest.mock import patch

def _login_superadmin(client_fixture, db):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="super@tap.com", name="Super", role="superadmin", password_hash=pw)
    db.session.add(m); db.session.commit()
    client_fixture.post("/auth/login", data={"email": "super@tap.com", "password": "pw"})

def test_access_page_returns_200(client, db):
    _login_superadmin(client, db)
    r = client.get("/admin/access/")
    assert r.status_code == 200

@patch("routes.access.send_invitation")
def test_invite_team_member_creates_pending_record(mock_send, client, db):
    _login_superadmin(client, db)
    r = client.post("/admin/access/invite",
        data={"email": "new@tap.com", "name": "New User", "role": "user"},
        follow_redirects=True)
    assert r.status_code == 200
    m = TeamMember.query.filter_by(email="new@tap.com").first()
    assert m is not None
    assert m.invite_token is not None
    assert mock_send.called

def test_revoke_team_member_clears_password(client, db):
    _login_superadmin(client, db)
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="user@tap.com", name="U", role="user", password_hash=pw)
    db.session.add(m); db.session.commit()
    r = client.post(f"/admin/access/revoke/{m.id}", follow_redirects=True)
    db.session.refresh(m)
    assert m.password_hash is None

def test_generate_client_portal_link_rotates_token(client, db):
    _login_superadmin(client, db)
    c = Client(name="X", slug="x"); db.session.add(c); db.session.commit()
    old_token = c.secret_token
    r = client.post(f"/admin/access/client/{c.id}/rotate-token", follow_redirects=True)
    db.session.refresh(c)
    assert c.secret_token != old_token
