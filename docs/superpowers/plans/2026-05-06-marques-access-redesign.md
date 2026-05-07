# Marques & Accès Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le système double (TeamMember + ClientUser, portail séparé) par un système unifié — un seul modèle utilisateur avec rôles `admin` / `client`, un seul login, tout accessible via `/admin/`.

**Architecture:** Supprimer `ClientUser` et le portail `/client/`. Tous les utilisateurs (équipe et clients) se connectent via `/auth/login` et voient `/admin/` filtré selon leur rôle. "Client" (l'entité en DB) est renommée "Marque" uniquement dans l'UI.

**Tech Stack:** Flask, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-Login, Jinja2, HTMX, pytest

---

## File Map

| Fichier | Action | Ce qui change |
|---|---|---|
| `models.py` | Modifier | Supprimer `ClientUser`, `can_see_client()` role check |
| `decorators.py` | Modifier | Aucun changement de code — les appels aux routes changent |
| `routes/admin.py` | Modifier | `/admin/client/<id>` → `/admin/marque/<id>`, role checks |
| `routes/api.py` | Modifier | `/api/client/<id>/chart` → `/api/marque/<id>/chart`, role checks |
| `routes/access.py` | Modifier | Supprimer `rotate_client_token`, nouvelle invite avec marques, nouveau `assign_brands`, ajouter `deactivate_client` |
| `routes/portal.py` | **Supprimer** | Portail client supprimé |
| `app.py` | Modifier | Supprimer enregistrement `portal_bp` |
| `templates/base.html` | Modifier | Cacher onglet "Accès" pour rôle `client` |
| `templates/admin/dashboard.html` | Modifier | "Clients" → "Marques", URL `/admin/client/` → `/admin/marque/` |
| `templates/admin/client_detail.html` | **Renommer** → `marque_detail.html` | URL chart mis à jour |
| `templates/admin/access.html` | Réécrire | Sections Marques + Utilisateurs unifiées |
| `templates/portal/` | **Supprimer** | `client.html`, `login.html` |
| `migrations/versions/` | Créer | Migration Alembic : rôles + fusion ClientUser |
| `tests/test_models.py` | Modifier | Supprimer refs ClientUser, rôles mis à jour |
| `tests/test_decorators.py` | Modifier | Rôles et routes mis à jour |
| `tests/test_admin_routes.py` | Modifier | URL `/admin/marque/<id>`, rôle `admin` |
| `tests/test_api_routes.py` | Modifier | URL `/api/marque/<id>/chart` |
| `tests/test_access_routes.py` | Modifier | Nouvelle logique invite + marques |
| `tests/test_portal_routes.py` | **Supprimer** | Portail supprimé |

---

## Task 1: Update models — supprimer ClientUser, mettre à jour les rôles

**Files:**
- Modify: `models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Écrire les tests mis à jour (ils failent avec le code actuel)**

Remplacer entièrement `tests/test_models.py` par :

```python
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
```

- [ ] **Step 2: Lancer les tests pour confirmer qu'ils failent**

```bash
cd /c/Users/phili/meta_ads_dashboard
python -m pytest tests/test_models.py -v
```

Résultat attendu : FAILED — `ImportError: cannot import name 'ClientUser'`

- [ ] **Step 3: Mettre à jour `models.py`**

Supprimer la classe `ClientUser` entière (lignes 52-60) et mettre à jour `can_see_client()` :

```python
from datetime import datetime, UTC
import uuid
from flask_login import UserMixin
from extensions import db


class Client(db.Model):
    __tablename__ = "clients"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    meta_account_id = db.Column(db.String(50))
    google_customer_id = db.Column(db.String(50))
    secret_token = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    metrics = db.relationship("AdMetric", backref="client", lazy="dynamic", cascade="all, delete-orphan")
    sync_logs = db.relationship("SyncLog", backref="client", lazy="dynamic", cascade="all, delete-orphan")


class TeamMember(db.Model, UserMixin):
    __tablename__ = "team_members"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin | client
    invite_token = db.Column(db.String(36))
    invite_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
    last_login_at = db.Column(db.DateTime)

    assigned_clients = db.relationship("TeamMemberClient", backref="member", lazy="dynamic", cascade="all, delete-orphan")

    def can_see_client(self, client_id):
        if self.role == "admin":
            return True
        return self.assigned_clients.filter_by(client_id=client_id).first() is not None


class TeamMemberClient(db.Model):
    __tablename__ = "team_member_clients"
    id = db.Column(db.Integer, primary_key=True)
    team_member_id = db.Column(db.Integer, db.ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint("team_member_id", "client_id", name="uq_tmc_member_client"),
    )


class AdMetric(db.Model):
    __tablename__ = "ad_metrics"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    platform = db.Column(db.String(10), nullable=False)  # meta | google
    level = db.Column(db.String(10), nullable=False)      # campaign | adset | ad
    date = db.Column(db.Date, nullable=False)
    campaign_id = db.Column(db.String(50))
    campaign_name = db.Column(db.String(200))
    adset_id = db.Column(db.String(50))
    adset_name = db.Column(db.String(200))
    ad_id = db.Column(db.String(50))
    ad_name = db.Column(db.String(200))
    impressions = db.Column(db.Integer, default=0)
    reach = db.Column(db.Integer, default=0)
    frequency = db.Column(db.Float, default=0.0)
    clicks = db.Column(db.Integer, default=0)
    ctr = db.Column(db.Float, default=0.0)
    cpc = db.Column(db.Float, default=0.0)
    cpm = db.Column(db.Float, default=0.0)
    spend = db.Column(db.Float, default=0.0)
    purchases = db.Column(db.Integer, default=0)
    revenue = db.Column(db.Float, default=0.0)
    roas = db.Column(db.Float, default=0.0)
    synced_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())


class SyncLog(db.Model):
    __tablename__ = "sync_logs"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    platform = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # success | error
    rows_fetched = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    ran_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
```

- [ ] **Step 4: Lancer les tests — doivent passer**

```bash
python -m pytest tests/test_models.py -v
```

Résultat attendu : 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "refactor: remove ClientUser model, update role semantics to admin/client"
```

---

## Task 2: Mettre à jour routes admin + API (rôles + URL)

**Files:**
- Modify: `routes/admin.py`
- Modify: `routes/api.py`
- Modify: `tests/test_admin_routes.py`
- Modify: `tests/test_api_routes.py`
- Modify: `tests/test_decorators.py`

- [ ] **Step 1: Écrire les tests admin mis à jour**

Remplacer entièrement `tests/test_admin_routes.py` par :

```python
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
    c2 = _seed_marque(db, name="Marque Cachée", slug="cachee")
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
```

- [ ] **Step 2: Écrire les tests API mis à jour**

Remplacer entièrement `tests/test_api_routes.py` par :

```python
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
```

- [ ] **Step 3: Écrire les tests decorators mis à jour**

Remplacer entièrement `tests/test_decorators.py` par :

```python
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
    assert r.status_code == 403
```

- [ ] **Step 4: Lancer les tests — confirmer qu'ils failent**

```bash
python -m pytest tests/test_admin_routes.py tests/test_api_routes.py tests/test_decorators.py -v
```

Résultat attendu : plusieurs FAILED — routes pas encore renommées, rôles pas encore mis à jour.

- [ ] **Step 5: Mettre à jour `routes/admin.py`**

Remplacer entièrement `routes/admin.py` par :

```python
from datetime import date, timedelta
from flask import Blueprint, render_template, request, abort
from flask_login import current_user
from decorators import require_role
from sqlalchemy import func
from models import Client, AdMetric, SyncLog
from extensions import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

RANGE_OPTIONS = [
    ("today",     "Aujourd'hui"),
    ("yesterday", "Hier"),
    ("7d",        "7 derniers jours"),
    ("30d",       "30 derniers jours"),
    ("90d",       "90 derniers jours"),
    ("this_year", "Cette année"),
    ("ytd",       "Cumul annuel"),
    ("custom",    "Personnaliser"),
]


def _date_range(range_str, custom_start=None, custom_end=None):
    today = date.today()
    if range_str == "today":
        return today, today
    if range_str == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if range_str == "7d":
        return today - timedelta(days=7), today
    if range_str == "90d":
        return today - timedelta(days=90), today
    if range_str in ("this_year", "ytd"):
        return date(today.year, 1, 1), today
    if range_str == "custom":
        try:
            return date.fromisoformat(custom_start), date.fromisoformat(custom_end)
        except (ValueError, TypeError):
            return today - timedelta(days=30), today
    return today - timedelta(days=30), today


def _roas_class(roas):
    if roas >= 4:  return "roas-good"
    if roas >= 2:  return "roas-ok"
    return "roas-bad"


def _aggregate_metrics(client_id, level, start, end):
    base_agg = [
        func.sum(AdMetric.spend).label("spend"),
        func.sum(AdMetric.revenue).label("revenue"),
        func.sum(AdMetric.clicks).label("clicks"),
        func.sum(AdMetric.impressions).label("impressions"),
        func.sum(AdMetric.purchases).label("purchases"),
        func.sum(AdMetric.reach).label("reach"),
    ]
    base_filter = [
        AdMetric.client_id == client_id,
        AdMetric.level == level,
        AdMetric.date >= start,
        AdMetric.date <= end,
    ]

    if level == "campaign":
        cols = [AdMetric.campaign_id, AdMetric.campaign_name, AdMetric.platform]
    elif level == "adset":
        cols = [AdMetric.adset_id, AdMetric.adset_name,
                AdMetric.campaign_name, AdMetric.platform]
    else:  # ad
        cols = [AdMetric.ad_id, AdMetric.ad_name,
                AdMetric.adset_name, AdMetric.campaign_name, AdMetric.platform]

    rows = (db.session.query(*cols, *base_agg)
            .filter(*base_filter)
            .group_by(*cols)
            .order_by(func.sum(AdMetric.spend).desc())
            .all())

    result = []
    for r in rows:
        spend       = float(r.spend or 0)
        revenue     = float(r.revenue or 0)
        clicks      = int(r.clicks or 0)
        impressions = int(r.impressions or 0)
        purchases   = int(r.purchases or 0)
        base = {
            "campaign_id": None, "campaign_name": None,
            "adset_id": None,    "adset_name": None,
            "ad_id": None,       "ad_name": None,
            "platform": r.platform,
            "spend": spend, "revenue": revenue, "clicks": clicks,
            "impressions": impressions, "purchases": purchases,
            "ctr":  round(clicks / impressions * 100, 2) if impressions else 0,
            "cpc":  round(spend / clicks, 2) if clicks else 0,
            "cpm":  round(spend / impressions * 1000, 2) if impressions else 0,
            "roas": round(revenue / spend, 2) if spend else 0,
        }
        if level == "campaign":
            base.update({"campaign_id": r.campaign_id, "campaign_name": r.campaign_name})
        elif level == "adset":
            base.update({"adset_id": r.adset_id, "adset_name": r.adset_name,
                         "campaign_name": r.campaign_name})
        else:
            base.update({"ad_id": r.ad_id, "ad_name": r.ad_name,
                         "adset_name": r.adset_name, "campaign_name": r.campaign_name})
        result.append(base)
    return result


@admin_bp.route("/")
@require_role("admin", "client")
def dashboard():
    range_str = request.args.get("range", "30d")
    platform  = request.args.get("platform", "all")
    custom_start = request.args.get("start", "")
    custom_end   = request.args.get("end", "")
    start, end = _date_range(range_str, custom_start, custom_end)

    clients = Client.query.filter_by(is_active=True).all()
    if current_user.role == "client":
        allowed = {tc.client_id for tc in current_user.assigned_clients}
        clients = [c for c in clients if c.id in allowed]

    q = (db.session.query(
            AdMetric.client_id,
            func.sum(AdMetric.spend).label("spend"),
            func.sum(AdMetric.revenue).label("revenue"),
            func.sum(AdMetric.clicks).label("clicks"),
            func.sum(AdMetric.purchases).label("purchases"),
        )
        .filter(AdMetric.date >= start, AdMetric.date <= end, AdMetric.level == "campaign")
    )
    if platform != "all":
        q = q.filter(AdMetric.platform == platform)
    rows = {r.client_id: r for r in q.group_by(AdMetric.client_id).all()}

    last_sync = {
        s.client_id: s.ran_at
        for s in db.session.query(
            SyncLog.client_id,
            func.max(SyncLog.ran_at).label("ran_at")
        ).group_by(SyncLog.client_id).all()
    }

    client_data = []
    for c in clients:
        r = rows.get(c.id)
        spend = float(r.spend or 0) if r else 0
        revenue = float(r.revenue or 0) if r else 0
        clicks = int(r.clicks or 0) if r else 0
        roas = round(revenue / spend, 2) if spend else 0
        client_data.append({
            "client": c,
            "spend": spend,
            "revenue": revenue,
            "clicks": clicks,
            "roas": roas,
            "roas_class": _roas_class(roas),
            "last_sync": last_sync.get(c.id),
        })

    client_data.sort(key=lambda x: x["spend"], reverse=True)

    global_spend   = sum(x["spend"] for x in client_data)
    global_revenue = sum(x["revenue"] for x in client_data)
    global_clicks  = sum(x["clicks"] for x in client_data)
    global_roas    = round(global_revenue / global_spend, 2) if global_spend else 0

    return render_template("admin/dashboard.html",
        client_data=client_data, range=range_str, platform=platform,
        range_options=RANGE_OPTIONS, custom_start=custom_start, custom_end=custom_end,
        global_spend=global_spend, global_revenue=global_revenue,
        global_clicks=global_clicks, global_roas=global_roas,
        active_count=len(clients),
    )


@admin_bp.route("/marque/<int:client_id>")
@require_role("admin", "client")
def marque_detail(client_id):
    if not current_user.can_see_client(client_id):
        abort(403)
    c = db.session.get(Client, client_id)
    if c is None:
        abort(404)
    range_str    = request.args.get("range", "30d")
    custom_start = request.args.get("start", "")
    custom_end   = request.args.get("end", "")
    view         = request.args.get("view", "campaign")
    if view not in ("campaign", "adset", "ad"):
        view = "campaign"
    start, end = _date_range(range_str, custom_start, custom_end)

    rows = _aggregate_metrics(c.id, view, start, end)
    sync_history = SyncLog.query.filter_by(client_id=c.id).order_by(SyncLog.ran_at.desc()).limit(20).all()

    spend   = sum(r["spend"]   for r in rows)
    revenue = sum(r["revenue"] for r in rows)
    clicks  = sum(r["clicks"]  for r in rows)
    roas    = round(revenue / spend, 2) if spend else 0

    return render_template("admin/marque_detail.html",
        c=c, rows=rows, sync_history=sync_history,
        range=range_str, range_options=RANGE_OPTIONS,
        custom_start=custom_start, custom_end=custom_end,
        view=view,
        spend=spend, revenue=revenue, clicks=clicks, roas=roas,
        roas_class=_roas_class(roas),
    )
```

- [ ] **Step 6: Mettre à jour `routes/api.py`**

Remplacer entièrement `routes/api.py` par :

```python
from datetime import date, timedelta
from collections import defaultdict
from flask import Blueprint, jsonify, request, abort, current_app
from flask_login import login_required, current_user
from models import Client, AdMetric
from extensions import db
from sqlalchemy import func
import threading

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/marque/<int:client_id>/chart")
@login_required
def client_chart(client_id):
    if not current_user.can_see_client(client_id):
        abort(403)
    from routes.admin import _date_range
    range_str = request.args.get("range", "30d")
    start, end = _date_range(range_str, request.args.get("start"), request.args.get("end"))

    rows = (db.session.query(AdMetric.date, AdMetric.platform, func.sum(AdMetric.spend))
        .filter(AdMetric.client_id == client_id, AdMetric.level == "campaign",
                AdMetric.date >= start, AdMetric.date <= end)
        .group_by(AdMetric.date, AdMetric.platform)
        .order_by(AdMetric.date)
        .all())

    by_date = defaultdict(lambda: {"meta": 0.0, "google": 0.0})
    for row_date, platform, spend in rows:
        by_date[str(row_date)][platform] = round(float(spend), 2)

    labels = sorted(by_date.keys())
    return jsonify({
        "labels": labels,
        "meta":   [by_date[d]["meta"]   for d in labels],
        "google": [by_date[d]["google"] for d in labels],
    })


@api_bp.route("/sync/<int:client_id>", methods=["POST"])
@login_required
def manual_sync(client_id):
    if not current_user.can_see_client(client_id):
        abort(403)
    c = db.session.get(Client, client_id)
    if c is None:
        abort(404)
    from sync import sync_client
    errors = sync_client(c)
    if errors:
        return jsonify({"status": "error", "errors": errors}), 200
    return jsonify({"status": "ok"})


@api_bp.route("/sync/all", methods=["POST"])
@login_required
def manual_sync_all():
    if current_user.role != "admin":
        abort(403)
    from sync import sync_all_clients
    app = current_app._get_current_object()
    t = threading.Thread(target=sync_all_clients, args=[app])
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})
```

- [ ] **Step 7: Lancer tous les tests mis à jour — doivent passer**

```bash
python -m pytest tests/test_admin_routes.py tests/test_api_routes.py tests/test_decorators.py tests/test_models.py -v
```

Résultat attendu : tous PASSED (le test portal va encore échouer mais on le supprime à Task 4).

- [ ] **Step 8: Commit**

```bash
git add routes/admin.py routes/api.py tests/test_admin_routes.py tests/test_api_routes.py tests/test_decorators.py
git commit -m "refactor: rename /admin/client → /admin/marque, update roles to admin/client"
```

---

## Task 3: Réécrire `routes/access.py` — nouvelle invite + brand assignment

**Files:**
- Modify: `routes/access.py`
- Modify: `tests/test_access_routes.py`

- [ ] **Step 1: Écrire les tests d'accès mis à jour**

Remplacer entièrement `tests/test_access_routes.py` par :

```python
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
```

- [ ] **Step 2: Lancer les tests — confirmer qu'ils failent**

```bash
python -m pytest tests/test_access_routes.py -v
```

Résultat attendu : plusieurs FAILED — routes manquantes (`deactivate_client`, `assign_brands`), logique invite pas encore mise à jour.

- [ ] **Step 3: Réécrire `routes/access.py`**

Remplacer entièrement `routes/access.py` par :

```python
import uuid
import bcrypt
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from models import TeamMember, Client, TeamMemberClient
from extensions import db
from decorators import require_role
from mailer import send_invitation

access_bp = Blueprint("access", __name__, url_prefix="/admin/access")


@access_bp.route("/")
@require_role("admin")
def index():
    members = TeamMember.query.order_by(TeamMember.created_at).all()
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()
    client_map = {c.id: c for c in clients}
    member_brands = {
        m.id: {tc.client_id for tc in m.assigned_clients}
        for m in members if m.role == "client"
    }
    from fetchers.meta_fetcher import fetch_ad_accounts
    try:
        meta_accounts = fetch_ad_accounts()
    except Exception:
        meta_accounts = []
    return render_template("admin/access.html",
        members=members, clients=clients, client_map=client_map,
        member_brands=member_brands, current_member=current_user,
        meta_accounts=meta_accounts)


@access_bp.route("/invite", methods=["POST"])
@require_role("admin")
def invite():
    email = request.form.get("email", "").strip().lower()
    name  = request.form.get("name", "").strip()
    role  = request.form.get("role", "admin")
    if role not in ("admin", "client"):
        role = "admin"
    if TeamMember.query.filter_by(email=email).first():
        flash("Cet email est déjà enregistré.")
        return redirect(url_for("access.index"))
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=48)
    m = TeamMember(email=email, name=name, role=role, invite_token=token, invite_expires_at=expires)
    db.session.add(m)
    db.session.flush()
    if role == "client":
        for brand_id in request.form.getlist("brand_ids"):
            try:
                db.session.add(TeamMemberClient(team_member_id=m.id, client_id=int(brand_id)))
            except (ValueError, Exception):
                pass
    db.session.commit()
    invite_url = url_for("access.accept_invite", token=token, _external=True)
    send_invitation(email, name, invite_url)
    flash(f"Invitation envoyée à {email}.")
    return redirect(url_for("access.index"))


@access_bp.route("/accept/<string:token>", methods=["GET", "POST"])
def accept_invite(token):
    m = TeamMember.query.filter_by(invite_token=token).first_or_404()
    if m.invite_expires_at < datetime.utcnow():
        flash("Ce lien d'invitation a expiré.")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        pw = request.form.get("password", "")
        m.password_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        m.invite_token = None
        m.invite_expires_at = None
        db.session.commit()
        flash("Compte créé ! Tu peux te connecter.")
        return redirect(url_for("auth.login"))
    return render_template("auth/accept_invite.html", member=m)


@access_bp.route("/revoke/<int:member_id>", methods=["POST"])
@require_role("admin")
def revoke(member_id):
    m = db.session.get(TeamMember, member_id)
    if m is None:
        abort(404)
    m.password_hash = None
    m.invite_token = None
    db.session.commit()
    flash(f"Accès révoqué pour {m.name}.")
    return redirect(url_for("access.index"))


@access_bp.route("/client/new", methods=["POST"])
@require_role("admin")
def new_client():
    name = request.form.get("name", "").strip()
    meta_id   = request.form.get("meta_account_id", "").strip() or None
    google_id = request.form.get("google_customer_id", "").strip() or None
    slug = name.lower().replace(" ", "-")
    c = Client(name=name, slug=slug, meta_account_id=meta_id, google_customer_id=google_id)
    db.session.add(c); db.session.commit()
    flash(f"Marque '{name}' ajoutée.")
    return redirect(url_for("access.index"))


@access_bp.route("/client/<int:client_id>/deactivate", methods=["POST"])
@require_role("admin")
def deactivate_client(client_id):
    c = db.session.get(Client, client_id)
    if c is None:
        abort(404)
    c.is_active = False
    db.session.commit()
    flash(f"Marque '{c.name}' désactivée.")
    return redirect(url_for("access.index"))


@access_bp.route("/assign-brands/<int:member_id>", methods=["POST"])
@require_role("admin")
def assign_brands(member_id):
    m = db.session.get(TeamMember, member_id)
    if m is None or m.role != "client":
        abort(404)
    TeamMemberClient.query.filter_by(team_member_id=m.id).delete()
    for brand_id in request.form.getlist("brand_ids"):
        try:
            db.session.add(TeamMemberClient(team_member_id=m.id, client_id=int(brand_id)))
        except ValueError:
            pass
    db.session.commit()
    flash(f"Marques mises à jour pour {m.name}.")
    return redirect(url_for("access.index"))
```

- [ ] **Step 4: Lancer les tests access — doivent passer**

```bash
python -m pytest tests/test_access_routes.py -v
```

Résultat attendu : 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add routes/access.py tests/test_access_routes.py
git commit -m "feat: rewrite access routes — brand assignment, deactivate, unified invite"
```

---

## Task 4: Supprimer le portail client

**Files:**
- Delete: `routes/portal.py`
- Delete: `templates/portal/client.html`
- Delete: `templates/portal/login.html`
- Delete: `tests/test_portal_routes.py`
- Modify: `app.py`

- [ ] **Step 1: Supprimer les fichiers portal**

```bash
rm /c/Users/phili/meta_ads_dashboard/routes/portal.py
rm /c/Users/phili/meta_ads_dashboard/templates/portal/client.html
rm /c/Users/phili/meta_ads_dashboard/templates/portal/login.html
rm /c/Users/phili/meta_ads_dashboard/tests/test_portal_routes.py
```

- [ ] **Step 2: Mettre à jour `app.py` — supprimer portal_bp**

Remplacer entièrement `app.py` par :

```python
from flask import Flask
from config import Config
from extensions import db, login_manager, migrate


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    import models  # noqa: F401

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.access import access_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(access_bp)
    app.register_blueprint(api_bp)

    if not app.testing:
        from sync import init_scheduler
        init_scheduler(app)

    _ensure_columns(app)

    return app


def _ensure_columns(app):
    with app.app_context():
        from sqlalchemy import text
        try:
            db.session.execute(text(
                "ALTER TABLE ad_metrics ADD COLUMN IF NOT EXISTS ad_id VARCHAR(50)"
            ))
            db.session.execute(text(
                "ALTER TABLE ad_metrics ADD COLUMN IF NOT EXISTS ad_name VARCHAR(200)"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()


app = create_app()
```

- [ ] **Step 3: Lancer la suite de tests complète — vérifier qu'il n'y a pas de régression**

```bash
python -m pytest tests/ -v --ignore=tests/test_portal_routes.py 2>/dev/null || python -m pytest tests/ -v
```

Résultat attendu : tous PASSED (test_portal_routes.py n'existe plus, tous les autres passent).

- [ ] **Step 4: Commit**

```bash
git add app.py routes/ templates/portal/ tests/
git commit -m "feat: remove client portal — all users access via /admin/"
```

---

## Task 5: Mettre à jour les templates

**Files:**
- Modify: `templates/base.html`
- Modify: `templates/admin/dashboard.html`
- Create: `templates/admin/marque_detail.html` (copie de client_detail.html mise à jour)
- Delete: `templates/admin/client_detail.html`
- Rewrite: `templates/admin/access.html`

- [ ] **Step 1: Mettre à jour `templates/base.html` — cacher Accès pour les clients**

Remplacer la nav par :

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}AdBoard{% endblock %} — Tête à Papineau</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/tap.css') }}">
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
</head>
<body>
  <nav class="nav">
    <div>
      <div class="nav-brand-name">Tête à Papineau</div>
      <div class="nav-brand-sub">AdBoard</div>
    </div>
    {% if current_user.is_authenticated %}
      <a class="nav-link {% if request.endpoint == 'admin.dashboard' %}active{% endif %}" href="{{ url_for('admin.dashboard') }}">Vue globale</a>
      {% if current_user.role == 'admin' %}
        <a class="nav-link {% if request.blueprint == 'access' %}active{% endif %}" href="{{ url_for('access.index') }}">Accès</a>
      {% endif %}
    {% endif %}
    <div class="nav-right">
      {% block nav_right %}
        {% if current_user.is_authenticated %}
          <a href="{{ url_for('auth.change_password') }}" style="font-size:11px;color:var(--beige);opacity:.7;text-decoration:none;">{{ current_user.name }}</a>
          <a href="{{ url_for('auth.logout') }}" class="btn btn-outline" style="font-size:11px;padding:4px 10px;">Déconnexion</a>
        {% endif %}
      {% endblock %}
    </div>
  </nav>
  <div class="main">
    {% for msg in get_flashed_messages() %}
      <div class="flash-error">{{ msg }}</div>
    {% endfor %}
    {% block content %}{% endblock %}
  </div>
</body>
</html>
```

- [ ] **Step 2: Mettre à jour `templates/admin/dashboard.html` — Clients → Marques, URL mise à jour**

Remplacer les occurrences suivantes dans `dashboard.html` :

1. `window.location='/admin/client/{{ row.client.id }}?range={{ range }}'` → `window.location='/admin/marque/{{ row.client.id }}?range={{ range }}'`
2. `<span class="card-title">Tous les clients</span>` → `<span class="card-title">Toutes les marques</span>`
3. `<th>Client</th>` → `<th>Marque</th>`
4. `<td colspan="7" style="text-align:center;color:var(--gris);padding:24px">Aucun client — ajoutes-en un dans Accès.</td>` → `<td colspan="7" style="text-align:center;color:var(--gris);padding:24px">Aucune marque — ajoutes-en une dans Accès.</td>`
5. `<div class="kpi-label">Clients actifs</div>` → `<div class="kpi-label">Marques actives</div>`

Contenu complet de `templates/admin/dashboard.html` après mise à jour :

```html
{% extends "base.html" %}
{% block title %}Vue globale{% endblock %}
{% block content %}

<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h1 style="font-size:18px;font-weight:700">Vue globale</h1>
</div>

<!-- Filters -->
<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap">
  <span style="font-size:11px;color:var(--gris);text-transform:uppercase;letter-spacing:1px">Période :</span>
  <select id="range-select" onchange="onRangeChange(this.value)"
          style="font-size:13px;padding:4px 8px;border:1px solid var(--beige);border-radius:6px;background:white;color:var(--brun);cursor:pointer">
    {% for val, label in range_options %}
      <option value="{{ val }}" {% if range==val %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
  <div style="width:1px;height:20px;background:var(--beige);margin:0 8px"></div>
  <span style="font-size:11px;color:var(--gris);text-transform:uppercase;letter-spacing:1px">Plateforme :</span>
  {% for p,l in [("all","Toutes"),("meta","Meta"),("google","Google")] %}
    <a href="?range={{ range }}{% if range=='custom' %}&start={{ custom_start }}&end={{ custom_end }}{% endif %}&platform={{ p }}" class="pill {% if platform==p %}active{% endif %}">{{ l }}</a>
  {% endfor %}
</div>
<div id="custom-dates" style="display:{% if range=='custom' %}flex{% else %}none{% endif %};align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap">
  <span style="font-size:11px;color:var(--gris)">Du</span>
  <input type="date" id="start-date" value="{{ custom_start }}"
         style="font-size:13px;padding:4px 8px;border:1px solid var(--beige);border-radius:6px;color:var(--brun)">
  <span style="font-size:11px;color:var(--gris)">au</span>
  <input type="date" id="end-date" value="{{ custom_end }}"
         style="font-size:13px;padding:4px 8px;border:1px solid var(--beige);border-radius:6px;color:var(--brun)">
  <button onclick="applyCustomRange()" class="btn btn-outline" style="font-size:13px;padding:4px 14px">Appliquer</button>
</div>
<script>
function syncClient(id) {
  const btn = document.getElementById('sync-' + id);
  btn.textContent = '…';
  btn.disabled = true;
  fetch('/api/sync/' + id, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'error') {
        btn.textContent = '⚠ ' + data.errors[0];
        btn.style.color = '#E95526';
        btn.disabled = false;
      } else {
        btn.textContent = '✓';
        btn.style.color = '#2d9e6b';
      }
    })
    .catch(() => { btn.textContent = '! Erreur réseau'; btn.disabled = false; });
}
function onRangeChange(val) {
  if (val === 'custom') {
    document.getElementById('custom-dates').style.display = 'flex';
  } else {
    window.location = '?range=' + val + '&platform={{ platform }}';
  }
}
function applyCustomRange() {
  const start = document.getElementById('start-date').value;
  const end   = document.getElementById('end-date').value;
  if (start && end) {
    window.location = '?range=custom&start=' + start + '&end=' + end + '&platform={{ platform }}';
  }
}
</script>
<div style="margin-bottom:20px"></div>

<!-- KPIs -->
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-label">Dépenses totales</div><div class="kpi-value">${{ "%.0f"|format(global_spend) }}</div></div>
  <div class="kpi"><div class="kpi-label">Revenus générés</div><div class="kpi-value">${{ "%.0f"|format(global_revenue) }}</div></div>
  <div class="kpi"><div class="kpi-label">ROAS moyen</div><div class="kpi-value accent">{{ global_roas }}x</div></div>
  <div class="kpi"><div class="kpi-label">Clics totaux</div><div class="kpi-value">{{ "{:,}".format(global_clicks) }}</div></div>
  <div class="kpi"><div class="kpi-label">Marques actives</div><div class="kpi-value">{{ active_count }}</div></div>
</div>

<!-- Marques table -->
<div class="card">
  <div class="card-header">
    <span class="card-title">Toutes les marques</span>
    <span class="card-meta">Classé par dépenses ↓</span>
  </div>
  <table>
    <thead><tr>
      <th>Marque</th><th>Plateformes</th>
      <th class="right">Dépenses</th><th class="right">Revenus</th>
      <th class="right">ROAS</th><th class="right">Clics</th>
      <th class="right">Sync</th>
    </tr></thead>
    <tbody>
    {% for row in client_data %}
      <tr onclick="window.location='/admin/marque/{{ row.client.id }}?range={{ range }}'">
        <td style="font-weight:600">{{ row.client.name }}</td>
        <td>
          {% if row.client.meta_account_id %}<span class="tag-meta">Meta</span>{% endif %}
          {% if row.client.google_customer_id %}<span class="tag-google">Google</span>{% endif %}
        </td>
        <td class="right">${{ "%.0f"|format(row.spend) }}</td>
        <td class="right">${{ "%.0f"|format(row.revenue) }}</td>
        <td class="right"><span class="{{ row.roas_class }}">{{ row.roas }}x</span></td>
        <td class="right">{{ "{:,}".format(row.clicks) }}</td>
        <td class="right" onclick="event.stopPropagation()">
          <button id="sync-{{ row.client.id }}" onclick="syncClient({{ row.client.id }})" class="btn btn-outline" style="font-size:11px;padding:2px 8px">↻ Sync</button>
          {% if row.last_sync %}
            <span class="sync-ok" style="font-size:11px;display:block">✓ {{ row.last_sync.strftime('%d/%m %H:%M') }}</span>
          {% else %}
            <span class="sync-err" style="font-size:11px;display:block">Jamais</span>
          {% endif %}
        </td>
      </tr>
    {% else %}
      <tr><td colspan="7" style="text-align:center;color:var(--gris);padding:24px">Aucune marque — ajoutes-en une dans Accès.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 3: Créer `templates/admin/marque_detail.html`**

C'est le même fichier que `client_detail.html` mais avec l'URL du chart mise à jour (`/api/client/` → `/api/marque/`).

Créer `templates/admin/marque_detail.html` avec ce contenu :

```html
{% extends "base.html" %}
{% block title %}{{ c.name }}{% endblock %}
{% block content %}
<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
  <a href="{{ url_for('admin.dashboard') }}" style="color:var(--gris);font-size:12px">← Retour</a>
  <h1 style="font-size:18px;font-weight:700">{{ c.name }}</h1>
  {% if c.meta_account_id %}<span class="tag-meta">Meta</span>{% endif %}
  {% if c.google_customer_id %}<span class="tag-google">Google</span>{% endif %}
  <div style="margin-left:auto">
    <button id="sync-btn" onclick="syncNow()" class="btn btn-outline">↻ Sync maintenant</button>
  </div>
</div>

<script>
function syncNow() {
  const btn = document.getElementById("sync-btn");
  btn.textContent = "Sync en cours...";
  btn.disabled = true;
  fetch("/api/sync/{{ c.id }}", { method: "POST" })
    .then(r => r.json())
    .then(data => {
      if (data.status === "error") {
        btn.textContent = "⚠ " + data.errors[0];
        btn.style.color = "#E95526";
        btn.disabled = false;
      } else {
        btn.textContent = "✓ Sync terminée — recharge la page";
        btn.style.color = "#2d9e6b";
        btn.style.borderColor = "#2d9e6b";
      }
    })
    .catch(() => {
      btn.textContent = "Erreur réseau — réessaie";
      btn.disabled = false;
    });
}
</script>

<!-- Period filter -->
<div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap">
  <select id="range-select" onchange="onRangeChange(this.value)"
          style="font-size:13px;padding:4px 8px;border:1px solid var(--beige);border-radius:6px;background:white;color:var(--brun);cursor:pointer">
    {% for val, label in range_options %}
      <option value="{{ val }}" {% if range==val %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
</div>
<div id="custom-dates" style="display:{% if range=='custom' %}flex{% else %}none{% endif %};align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap">
  <span style="font-size:11px;color:var(--gris)">Du</span>
  <input type="date" id="start-date" value="{{ custom_start }}"
         style="font-size:13px;padding:4px 8px;border:1px solid var(--beige);border-radius:6px;color:var(--brun)">
  <span style="font-size:11px;color:var(--gris)">au</span>
  <input type="date" id="end-date" value="{{ custom_end }}"
         style="font-size:13px;padding:4px 8px;border:1px solid var(--beige);border-radius:6px;color:var(--brun)">
  <button onclick="applyCustomRange()" class="btn btn-outline" style="font-size:13px;padding:4px 14px">Appliquer</button>
</div>
<div style="margin-bottom:20px"></div>
<script>
function onRangeChange(val) {
  if (val === 'custom') {
    document.getElementById('custom-dates').style.display = 'flex';
  } else {
    window.location = '?range=' + val;
  }
}
function applyCustomRange() {
  const start = document.getElementById('start-date').value;
  const end   = document.getElementById('end-date').value;
  if (start && end) {
    window.location = '?range=custom&start=' + start + '&end=' + end;
  }
}
</script>

<!-- KPIs -->
<div class="kpi-grid" style="grid-template-columns:repeat(4,1fr)">
  <div class="kpi"><div class="kpi-label">Budget dépensé</div><div class="kpi-value">${{ "%.2f"|format(spend) }}</div></div>
  <div class="kpi"><div class="kpi-label">Revenus</div><div class="kpi-value" style="color:#2d9e6b">${{ "%.2f"|format(revenue) }}</div></div>
  <div class="kpi"><div class="kpi-label">ROAS</div><div class="kpi-value accent">{{ roas }}x</div></div>
  <div class="kpi"><div class="kpi-label">Clics</div><div class="kpi-value">{{ "{:,}".format(clicks) }}</div></div>
</div>

<!-- Chart -->
<div class="card" style="margin-bottom:16px">
  <div class="card-header"><span class="card-title">Dépenses par jour</span></div>
  <div style="padding:16px;height:200px">
    <canvas id="spendChart"></canvas>
  </div>
</div>

<!-- View toggle -->
{% set base_q = '?range=' + range + ('&start=' + custom_start + '&end=' + custom_end if range == 'custom' else '') %}
<div style="display:flex;gap:8px;margin-bottom:16px">
  <a href="{{ base_q }}&view=campaign" class="pill {% if view=='campaign' %}active{% endif %}">Campagnes</a>
  <a href="{{ base_q }}&view=adset"    class="pill {% if view=='adset'    %}active{% endif %}">Groupes d'annonces</a>
  <a href="{{ base_q }}&view=ad"       class="pill {% if view=='ad'       %}active{% endif %}">Publicités</a>
</div>

<!-- Data table -->
<div class="card">
  <div class="card-header">
    <span class="card-title">
      {% if view == 'campaign' %}Campagnes
      {% elif view == 'adset' %}Groupes d'annonces
      {% else %}Publicités{% endif %}
    </span>
  </div>
  <table>
    <thead><tr>
      {% if view == 'ad' %}
        <th>Publicité</th><th>Groupe d'annonces</th><th>Campagne</th>
      {% elif view == 'adset' %}
        <th>Groupe d'annonces</th><th>Campagne</th>
      {% else %}
        <th>Campagne</th>
      {% endif %}
      <th></th>
      <th class="right">Dépenses</th><th class="right">Revenus</th>
      <th class="right">ROAS</th><th class="right">Clics</th>
      <th class="right">CTR</th><th class="right">CPC</th><th class="right">Impressions</th>
    </tr></thead>
    <tbody>
    {% for r in rows %}
      <tr>
        {% if view == 'ad' %}
          <td style="font-weight:600">{{ r.ad_name }}</td>
          <td style="font-size:11px;color:var(--gris)">{{ r.adset_name }}</td>
          <td style="font-size:11px;color:var(--gris)">{{ r.campaign_name }}</td>
        {% elif view == 'adset' %}
          <td style="font-weight:600">{{ r.adset_name }}</td>
          <td style="font-size:11px;color:var(--gris)">{{ r.campaign_name }}</td>
        {% else %}
          <td style="font-weight:600">{{ r.campaign_name }}</td>
        {% endif %}
        <td><span class="tag-{{ r.platform }}">{{ r.platform|capitalize }}</span></td>
        <td class="right">${{ "%.2f"|format(r.spend) }}</td>
        <td class="right">${{ "%.2f"|format(r.revenue) }}</td>
        <td class="right"><span class="{{ r.roas | float >= 4 and 'roas-good' or r.roas | float >= 2 and 'roas-ok' or 'roas-bad' }}">{{ r.roas }}x</span></td>
        <td class="right">{{ "{:,}".format(r.clicks) }}</td>
        <td class="right">{{ r.ctr }}%</td>
        <td class="right">${{ r.cpc }}</td>
        <td class="right">{{ "{:,}".format(r.impressions) }}</td>
      </tr>
    {% else %}
      <tr><td colspan="10" style="text-align:center;color:var(--gris);padding:24px">Aucune donnée pour cette période.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<!-- Sync logs -->
<div class="card" style="margin-top:16px">
  <div class="card-header"><span class="card-title">Historique des syncs</span></div>
  <table>
    <thead><tr><th>Date</th><th>Plateforme</th><th>Statut</th><th>Lignes</th><th>Erreur</th></tr></thead>
    <tbody>
    {% for s in sync_history %}
      <tr>
        <td style="font-size:12px">{{ s.ran_at.strftime('%Y-%m-%d %H:%M') }}</td>
        <td><span class="tag-{{ s.platform }}">{{ s.platform }}</span></td>
        <td><span class="{{ 'sync-ok' if s.status == 'success' else 'sync-err' }}">{{ s.status }}</span></td>
        <td class="right">{{ s.rows_fetched or 0 }}</td>
        <td style="font-size:11px;color:var(--gris);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ s.error_message or '' }}</td>
      </tr>
    {% else %}
      <tr><td colspan="5" style="text-align:center;color:var(--gris);padding:16px">Aucune sync enregistrée.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<script>
  fetch("/api/marque/{{ c.id }}/chart?range={{ range }}")
    .then(r => r.json())
    .then(data => {
      new Chart(document.getElementById("spendChart"), {
        type: "bar",
        data: {
          labels: data.labels,
          datasets: [
            { label: "Meta", data: data.meta, backgroundColor: "#E95526" },
            { label: "Google", data: data.google, backgroundColor: "#4285F4" },
          ]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } }
      });
    });
</script>
{% endblock %}
```

- [ ] **Step 4: Supprimer `templates/admin/client_detail.html`**

```bash
rm /c/Users/phili/meta_ads_dashboard/templates/admin/client_detail.html
```

- [ ] **Step 5: Réécrire `templates/admin/access.html`**

Remplacer entièrement avec le nouveau design Marques + Utilisateurs :

```html
{% extends "base.html" %}
{% block title %}Accès{% endblock %}
{% block content %}

<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h1 style="font-size:18px;font-weight:700">Gestion des accès</h1>
</div>

<!-- Section Marques -->
<div class="card" style="margin-bottom:20px">
  <div class="card-header">
    <span class="card-title">Marques ({{ clients|length }})</span>
    <button onclick="document.getElementById('brand-form').style.display='block'" class="btn btn-primary">+ Ajouter une marque</button>
  </div>

  <div id="brand-form" style="display:none;padding:16px;border-bottom:1px solid var(--bordure);background:var(--fond)">
    <form method="POST" action="{{ url_for('access.new_client') }}" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
      <div>
        <label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Nom</label>
        <input name="name" required placeholder="Boutique Lux" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px">
      </div>
      <div>
        <label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Compte Meta Ads</label>
        {% if meta_accounts %}
          <select name="meta_account_id" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px;min-width:220px">
            <option value="">— Aucun —</option>
            {% for a in meta_accounts %}
              <option value="{{ a.id }}">{{ a.name }} ({{ a.id }})</option>
            {% endfor %}
          </select>
        {% else %}
          <input name="meta_account_id" placeholder="act_123456" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px">
        {% endif %}
      </div>
      <div>
        <label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Google Customer ID</label>
        <input name="google_customer_id" placeholder="1234567890" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px">
      </div>
      <button type="submit" class="btn btn-primary">Ajouter</button>
    </form>
  </div>

  <table>
    <thead><tr><th>Marque</th><th>Plateformes</th><th>Actions</th></tr></thead>
    <tbody>
    {% for c in clients %}
      <tr>
        <td style="font-weight:600">{{ c.name }}</td>
        <td>
          {% if c.meta_account_id %}<span class="tag-meta">Meta</span>{% endif %}
          {% if c.google_customer_id %}<span class="tag-google">Google</span>{% endif %}
        </td>
        <td>
          <form method="POST" action="{{ url_for('access.deactivate_client', client_id=c.id) }}" style="display:inline"
                onsubmit="return confirm('Désactiver la marque {{ c.name }} ?')">
            <button class="btn btn-danger">Désactiver</button>
          </form>
        </td>
      </tr>
    {% else %}
      <tr><td colspan="3" style="text-align:center;color:var(--gris);padding:24px">Aucune marque active.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<!-- Section Utilisateurs -->
<div class="card">
  <div class="card-header">
    <span class="card-title">Utilisateurs ({{ members|length }})</span>
    <button onclick="document.getElementById('invite-form').style.display='block'" class="btn btn-primary">+ Inviter</button>
  </div>

  <div id="invite-form" style="display:none;padding:16px;border-bottom:1px solid var(--bordure);background:var(--fond)">
    <form method="POST" action="{{ url_for('access.invite') }}" style="display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap">
      <div>
        <label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Nom</label>
        <input name="name" required placeholder="Marie Leblanc" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px">
      </div>
      <div>
        <label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Email</label>
        <input name="email" type="email" required placeholder="marie@tap.com" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px">
      </div>
      <div>
        <label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Rôle</label>
        <select name="role" id="invite-role" onchange="toggleBrandPicker(this.value)"
                style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px">
          <option value="admin">Admin</option>
          <option value="client">Client</option>
        </select>
      </div>
      <div id="invite-brand-picker" style="display:none">
        <label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Marques assignées</label>
        <div style="display:flex;flex-direction:column;gap:4px;max-height:120px;overflow-y:auto;border:1px solid var(--bordure);border-radius:6px;padding:8px;background:white">
          {% for c in clients %}
            <label style="font-size:12px;display:flex;align-items:center;gap:6px;cursor:pointer">
              <input type="checkbox" name="brand_ids" value="{{ c.id }}"> {{ c.name }}
            </label>
          {% else %}
            <span style="font-size:12px;color:var(--gris)">Aucune marque disponible</span>
          {% endfor %}
        </div>
      </div>
      <div style="align-self:flex-end">
        <button type="submit" class="btn btn-primary">Envoyer l'invitation</button>
      </div>
    </form>
  </div>

  <table>
    <thead><tr><th>Utilisateur</th><th>Rôle</th><th>Marques</th><th>Statut</th><th>Dernière connexion</th><th>Actions</th></tr></thead>
    <tbody>
    {% for m in members %}
      <tr>
        <td>
          <div style="font-weight:600">{{ m.name }}</div>
          <div style="font-size:10px;color:var(--gris)">{{ m.email }}</div>
        </td>
        <td><span class="badge badge-{{ m.role }}">{{ 'Admin' if m.role == 'admin' else 'Client' }}</span></td>
        <td>
          {% if m.role == 'client' %}
            <div style="font-size:11px;color:var(--gris);margin-bottom:4px">
              {% set assigned = member_brands.get(m.id, set()) %}
              {% if assigned %}
                {% for cid in assigned %}{{ client_map[cid].name if cid in client_map else '?' }}{% if not loop.last %}, {% endif %}{% endfor %}
              {% else %}
                <span style="color:var(--gris)">Aucune</span>
              {% endif %}
            </div>
            <button onclick="document.getElementById('brands-{{ m.id }}').style.display = document.getElementById('brands-{{ m.id }}').style.display === 'none' ? 'block' : 'none'"
                    class="btn btn-outline" style="font-size:10px;padding:2px 8px">Modifier</button>
            <div id="brands-{{ m.id }}" style="display:none;margin-top:8px">
              <form method="POST" action="{{ url_for('access.assign_brands', member_id=m.id) }}"
                    style="display:flex;flex-direction:column;gap:4px">
                <div style="max-height:120px;overflow-y:auto;border:1px solid var(--bordure);border-radius:6px;padding:8px;background:white">
                  {% for c in clients %}
                    <label style="font-size:12px;display:flex;align-items:center;gap:6px;cursor:pointer">
                      <input type="checkbox" name="brand_ids" value="{{ c.id }}"
                             {% if c.id in member_brands.get(m.id, set()) %}checked{% endif %}>
                      {{ c.name }}
                    </label>
                  {% endfor %}
                </div>
                <button type="submit" class="btn btn-primary" style="font-size:11px;padding:4px 12px;align-self:flex-start">Sauvegarder</button>
              </form>
            </div>
          {% else %}
            <span style="font-size:11px;color:var(--gris)">Accès total</span>
          {% endif %}
        </td>
        <td>
          {% if m.password_hash %}<span class="sync-ok">● Actif</span>
          {% elif m.invite_token %}<span style="font-size:10px;color:#f39c12">◐ Invitation envoyée</span>
          {% else %}<span class="sync-err">Accès révoqué</span>{% endif %}
        </td>
        <td style="font-size:11px;color:var(--gris)">
          {{ m.last_login_at.strftime('%d %b à %H:%M') if m.last_login_at else '—' }}
        </td>
        <td>
          {% if m.id != current_member.id %}
          <form method="POST" action="{{ url_for('access.revoke', member_id=m.id) }}" style="display:inline"
                onsubmit="return confirm('Révoquer l\'accès de {{ m.name }} ?')">
            <button class="btn btn-danger">Révoquer</button>
          </form>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<script>
function toggleBrandPicker(role) {
  document.getElementById('invite-brand-picker').style.display = role === 'client' ? 'block' : 'none';
}
</script>
{% endblock %}
```

- [ ] **Step 6: Lancer la suite de tests complète**

```bash
python -m pytest tests/ -v
```

Résultat attendu : tous PASSED

- [ ] **Step 7: Commit**

```bash
git add templates/ tests/
git commit -m "feat: update templates — Marques terminology, unified access page, hide Accès for client role"
```

---

## Task 6: Migration de base de données Alembic

**Files:**
- Create: `migrations/versions/f7a8b9c0d1e2_marques_access_redesign.py`

Cette migration est nécessaire pour la **prod** (Railway/Neon PostgreSQL). En local avec SQLite, `db.create_all()` crée les tables à partir des modèles mis à jour. La migration fait trois choses : fusionner les rôles, migrer les `ClientUser` → `TeamMember`, supprimer `client_users`.

- [ ] **Step 1: Créer la migration**

Créer `migrations/versions/f7a8b9c0d1e2_marques_access_redesign.py` :

```python
"""marques access redesign — unify users, drop client_users

Revision ID: f7a8b9c0d1e2
Revises: d0620082110b
Create Date: 2026-05-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'd0620082110b'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Fusionner superadmin + user → admin (tous deviennent admin)
    op.execute("UPDATE team_members SET role = 'admin' WHERE role IN ('superadmin', 'user')")

    # 2. Migrer ClientUser → TeamMember avec role='client'
    #    ON CONFLICT: si email déjà présent (ex: doublon), on ignore
    op.execute("""
        INSERT INTO team_members (email, name, role, password_hash, created_at)
        SELECT cu.email, cu.email, 'client', cu.password_hash, cu.created_at
        FROM client_users cu
        WHERE NOT EXISTS (
            SELECT 1 FROM team_members tm WHERE tm.email = cu.email
        )
    """)

    # 3. Supprimer la table client_users
    op.drop_table('client_users')


def downgrade():
    op.create_table(
        'client_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
```

- [ ] **Step 2: Vérifier que la migration est bien chaînée**

```bash
cd /c/Users/phili/meta_ads_dashboard
python -m flask db history
```

Résultat attendu : `f7a8b9c0d1e2` apparaît dans la liste, chaîné après `d0620082110b`.

- [ ] **Step 3: Appliquer la migration en local (si SQLite — skip si pas de DB locale)**

```bash
python -m flask db upgrade
```

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/f7a8b9c0d1e2_marques_access_redesign.py
git commit -m "chore: add migration — merge roles, migrate ClientUser to TeamMember, drop client_users"
```

---

## Vérification finale

- [ ] **Lancer la suite complète de tests**

```bash
python -m pytest tests/ -v
```

Résultat attendu : 0 FAILED, 0 ERROR

- [ ] **Vérifier qu'il n'y a plus aucune référence à l'ancien code**

```bash
grep -r "ClientUser\|/client/\|portal_bp\|role.*superadmin\|role.*user\b" --include="*.py" /c/Users/phili/meta_ads_dashboard/ | grep -v ".pyc\|migrations\|__pycache__"
```

Résultat attendu : aucune ligne (ou uniquement des commentaires dans les migrations)

- [ ] **Vérifier l'app en local**

```bash
python -m flask run
```

Ouvrir http://localhost:5000/admin/ — se connecter en tant qu'admin, vérifier :
- L'onglet "Accès" est visible
- La page Accès affiche deux sections (Marques + Utilisateurs)
- Créer un utilisateur "Client", assigner une marque, vérifier l'affichage
- Se connecter en tant que ce client — vérifier que l'onglet "Accès" est caché et que seules ses marques sont visibles
- La page `/admin/marque/<id>` s'affiche correctement avec le bon chart

- [ ] **Déployer sur Railway**

```bash
git push origin main
```

Sur Railway, dans le terminal du service :
```bash
flask db upgrade
```

---

## Notes pour la migration en prod

Avant de déployer sur Railway :
1. Sauvegarder la base Neon (`pg_dump` ou snapshot Railway)
2. Déployer le nouveau code
3. Lancer `flask db upgrade` dans le terminal Railway — cela migre les rôles et supprime `client_users`
4. Les anciens `ClientUser` sont maintenant dans `team_members` avec `role='client'` mais sans marques assignées — les assigner manuellement via la nouvelle page Accès
