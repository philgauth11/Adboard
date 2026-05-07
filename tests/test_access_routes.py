import bcrypt
from models import TeamMember, Client, TeamMemberClient
from extensions import db
from unittest.mock import patch


def _login_admin(client_fixture, db):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="admin@tap.com", name="Admin", role="admin", password_hash=pw)
    db.session.add(m); db.session.commit()
    client_fixture.post("/auth/login", data={"email": "admin@tap.com", "password": "pw"})
    return m


def test_access_page_returns_200(client, db):
    _login_admin(client, db)
    r = client.get("/admin/access/")
    assert r.status_code == 200


def test_access_page_forbidden_for_client_role(client, db):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="c@tap.com", name="C", role="client", password_hash=pw)
    db.session.add(m); db.session.commit()
    client.post("/auth/login", data={"email": "c@tap.com", "password": "pw"})
    r = client.get("/admin/access/")
    assert r.status_code == 403


@patch("routes.access.send_invitation")
def test_invite_admin_creates_pending_record(mock_send, client, db):
    _login_admin(client, db)
    r = client.post("/admin/access/invite",
        data={"email": "new@tap.com", "name": "New Admin", "role": "admin"},
        follow_redirects=True)
    assert r.status_code == 200
    m = TeamMember.query.filter_by(email="new@tap.com").first()
    assert m is not None
    assert m.role == "admin"
    assert m.invite_token is not None
    assert mock_send.called


@patch("routes.access.send_invitation")
def test_invite_client_with_brand_assignment(mock_send, client, db):
    _login_admin(client, db)
    c = Client(name="Marque X", slug="marque-x"); db.session.add(c); db.session.commit()
    r = client.post("/admin/access/invite",
        data={"email": "client@marque.com", "name": "Client X",
              "role": "client", "brand_ids": str(c.id)},
        follow_redirects=True)
    assert r.status_code == 200
    m = TeamMember.query.filter_by(email="client@marque.com").first()
    assert m is not None
    assert m.role == "client"
    link = TeamMemberClient.query.filter_by(team_member_id=m.id, client_id=c.id).first()
    assert link is not None


def test_revoke_clears_password(client, db):
    _login_admin(client, db)
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="user@tap.com", name="U", role="client", password_hash=pw)
    db.session.add(m); db.session.commit()
    r = client.post(f"/admin/access/revoke/{m.id}", follow_redirects=True)
    db.session.refresh(m)
    assert m.password_hash is None


def test_add_marque_creates_client_record(client, db):
    _login_admin(client, db)
    r = client.post("/admin/access/client/new",
        data={"name": "Nouvelle Marque", "meta_account_id": "act_999"},
        follow_redirects=True)
    assert r.status_code == 200
    c = Client.query.filter_by(slug="nouvelle-marque").first()
    assert c is not None


def test_deactivate_marque(client, db):
    _login_admin(client, db)
    c = Client(name="Marque Active", slug="marque-active"); db.session.add(c); db.session.commit()
    r = client.post(f"/admin/access/client/{c.id}/deactivate", follow_redirects=True)
    db.session.refresh(c)
    assert c.is_active is False


def test_assign_brands_updates_client_links(client, db):
    _login_admin(client, db)
    c1 = Client(name="M1", slug="m1"); c2 = Client(name="M2", slug="m2")
    db.session.add_all([c1, c2]); db.session.commit()
    m = TeamMember(email="c@tap.com", name="C", role="client"); db.session.add(m); db.session.commit()
    # Assign only c1
    db.session.add(TeamMemberClient(team_member_id=m.id, client_id=c1.id)); db.session.commit()
    # Now reassign to c2 only
    r = client.post(f"/admin/access/assign-brands/{m.id}",
        data={"brand_ids": str(c2.id)}, follow_redirects=True)
    assert r.status_code == 200
    links = TeamMemberClient.query.filter_by(team_member_id=m.id).all()
    assert len(links) == 1
    assert links[0].client_id == c2.id
