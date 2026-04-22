import bcrypt
from models import TeamMember
from extensions import db
from flask_login import login_user


def _login(client_fixture, db, role="user", assigned_client_ids=None):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email=f"{role}@tap.com", name="Test", role=role, password_hash=pw)
    db.session.add(m)
    db.session.commit()
    if assigned_client_ids:
        for cid in assigned_client_ids:
            db.session.add(TeamMemberClient(team_member_id=m.id, client_id=cid))
        db.session.commit()
    client_fixture.post("/auth/login", data={"email": f"{role}@tap.com", "password": "pw"})
    return m


def test_superadmin_can_access_admin_dashboard(client, db):
    _login(client, db, role="superadmin")
    r = client.get("/admin/")
    assert r.status_code == 200


def test_unauthenticated_redirected_to_login(client):
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code == 302


def test_wrong_role_gets_403(client, db):
    _login(client, db, role="client")
    r = client.get("/admin/")
    assert r.status_code == 403
