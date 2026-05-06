from models import Client, TeamMember, TeamMemberClient, AdMetric, SyncLog
from datetime import date


def test_client_gets_secret_token_automatically(db):
    c = Client(name="Boutique Lux", slug="boutique-lux")
    db.session.add(c)
    db.session.commit()
    assert c.secret_token is not None
    assert len(c.secret_token) == 36


def test_admin_can_see_all_clients(db):
    c = Client(name="Client A", slug="client-a")
    db.session.add(c)
    db.session.commit()
    m = TeamMember(email="admin@tap.com", name="Admin", role="admin")
    db.session.add(m)
    db.session.commit()
    assert m.can_see_client(c.id) is True


def test_client_user_sees_only_assigned_clients(db):
    c1 = Client(name="Client A", slug="client-a")
    c2 = Client(name="Client B", slug="client-b")
    db.session.add_all([c1, c2])
    db.session.commit()
    m = TeamMember(email="user@tap.com", name="User", role="client")
    db.session.add(m)
    db.session.commit()
    link = TeamMemberClient(team_member_id=m.id, client_id=c1.id)
    db.session.add(link)
    db.session.commit()
    assert m.can_see_client(c1.id) is True
    assert m.can_see_client(c2.id) is False


def test_ad_metric_stores_all_fields(db):
    c = Client(name="Client A", slug="client-a")
    db.session.add(c)
    db.session.commit()
    m = AdMetric(
        client_id=c.id, platform="meta", level="campaign",
        date=date(2026, 4, 1), campaign_id="123", campaign_name="Spring Sale",
        impressions=10000, clicks=200, spend=100.0, revenue=500.0, roas=5.0,
    )
    db.session.add(m)
    db.session.commit()
    assert m.id is not None
    assert m.roas == 5.0
