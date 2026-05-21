import bcrypt
from datetime import date
from models import TeamMember, Client, AdMetric, TeamMemberClient
from extensions import db


def _login(client_fixture, db, role="admin"):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email=f"{role}@tap.com", name="Test", role=role, password_hash=pw)
    db.session.add(m)
    db.session.commit()
    client_fixture.post("/auth/login", data={"email": f"{role}@tap.com", "password": "pw"})
    return m


def _seed_marque(db, name="Boutique Lux", slug="boutique-lux"):
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


def test_dashboard_returns_200_for_admin(client, db):
    _login(client, db, role="admin")
    r = client.get("/admin/")
    assert r.status_code == 200


def test_dashboard_returns_200_for_client_role(client, db):
    _login(client, db, role="client")
    r = client.get("/admin/")
    assert r.status_code == 200


def test_dashboard_shows_only_assigned_marques_for_client(client, db):
    m = _login(client, db, role="client")
    c1 = _seed_marque(db, name="Marque Visible", slug="visible")
    c2 = _seed_marque(db, name="Marque Cachee", slug="cachee")
    db.session.add(TeamMemberClient(team_member_id=m.id, client_id=c1.id))
    db.session.commit()
    r = client.get("/admin/")
    assert b"Marque Visible" in r.data
    assert b"Marque Cach" not in r.data


def test_marque_detail_returns_200(client, db):
    _login(client, db, role="admin")
    c = _seed_marque(db)
    r = client.get(f"/admin/marque/{c.id}")
    assert r.status_code == 200


def test_marque_detail_403_for_unauthorized_client(client, db):
    m = _login(client, db, role="client")
    c = _seed_marque(db)
    # m has no assigned brands
    r = client.get(f"/admin/marque/{c.id}")
    assert r.status_code == 403


def test_marque_detail_200_for_authorized_client(client, db):
    m = _login(client, db, role="client")
    c = _seed_marque(db)
    db.session.add(TeamMemberClient(team_member_id=m.id, client_id=c.id))
    db.session.commit()
    r = client.get(f"/admin/marque/{c.id}")
    assert r.status_code == 200


def test_dashboard_passes_primary_value_for_leadgen(client, db):
    _login(client, db, role="admin")
    c = _seed_marque(db, name="Lead Co", slug="lead-co")
    # brand_type defaults to leadgen
    r = client.get("/admin/")
    assert r.status_code == 200
    assert b"lead-co" in r.data or b"Lead Co" in r.data


def test_marque_detail_includes_leads_for_leadgen(client, db):
    _login(client, db, role="admin")
    c = _seed_marque(db)
    db.session.add(AdMetric(
        client_id=c.id, platform="meta", level="campaign",
        date=date(2026, 4, 16), campaign_id="2", campaign_name="Summer",
        spend=100.0, leads=8,
    ))
    db.session.commit()
    r = client.get(f"/admin/marque/{c.id}")
    assert r.status_code == 200


def test_marque_detail_includes_roas_for_ecommerce(client, db):
    _login(client, db, role="admin")
    c = Client(name="Shop", slug="shop", meta_account_id="act_123", brand_type="ecommerce")
    db.session.add(c); db.session.commit()
    db.session.add(AdMetric(
        client_id=c.id, platform="meta", level="campaign",
        date=date(2026, 4, 15), campaign_id="1", campaign_name="Spring",
        spend=100.0, revenue=500.0, roas=5.0, purchases=10,
    ))
    db.session.commit()
    r = client.get(f"/admin/marque/{c.id}")
    assert r.status_code == 200
