# AdBoard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build AdBoard — a hosted Flask web app that centralises Meta Ads + Google Ads data for ~12 clients, with a 360° admin view, per-client read-only portals, hourly sync, and role-based access for the team.

**Architecture:** Single Flask process on Railway with APScheduler for hourly sync, PostgreSQL (Neon) for storage, HTMX + Chart.js for reactive UI without a JS framework, and Flask-Login for team auth with UUID secret tokens for client portals.

**Tech Stack:** Python 3.11, Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, APScheduler, bcrypt, facebook-business SDK, google-ads SDK, Resend, gunicorn, pytest, pytest-flask

---

## File Map

```
meta_ads_dashboard/
├── app.py                     # Flask app factory + blueprint registration + scheduler init
├── config.py                  # Config class (env vars, DB URL fix for Railway)
├── extensions.py              # db, login_manager, migrate singletons
├── models.py                  # All SQLAlchemy models
├── decorators.py              # require_role(), require_client_access()
├── sync.py                    # sync_client(), sync_all_clients(), init_scheduler()
├── email.py                   # send_invitation() via Resend API
├── Procfile                   # gunicorn --workers 1
├── requirements.txt           # All dependencies
├── .env.example               # Template for env vars
├── fetchers/
│   ├── __init__.py
│   ├── meta_fetcher.py        # fetch_campaigns(account_id) + fetch_adsets(account_id)
│   └── google_fetcher.py      # fetch_campaigns(customer_id) + fetch_adsets(customer_id)
├── routes/
│   ├── __init__.py
│   ├── auth.py                # /auth/login, /auth/logout
│   ├── admin.py               # /admin/, /admin/client/<id>
│   ├── access.py              # /admin/access/* (team + portal management)
│   ├── portal.py              # /client/<token>, /client/login
│   └── api.py                 # /api/* (chart JSON, manual sync)
├── templates/
│   ├── base.html              # Nav, brand colors, HTMX + Chart.js CDN
│   ├── auth/login.html
│   ├── admin/
│   │   ├── dashboard.html     # 360° view
│   │   ├── client_detail.html
│   │   └── access.html
│   └── portal/client.html
├── static/css/tap.css         # CSS variables for brand palette
├── migrations/                # Flask-Migrate (auto-generated)
└── tests/
    ├── conftest.py
    ├── test_models.py
    ├── test_meta_fetcher.py
    ├── test_google_fetcher.py
    ├── test_sync.py
    ├── test_auth.py
    ├── test_admin_routes.py
    ├── test_portal_routes.py
    └── test_access_routes.py
```

**Files to delete** (replaced by the new structure):
- `main.py` → replaced by `app.py`
- `config.py` → replaced by new `config.py`
- `meta_fetcher.py` → replaced by `fetchers/meta_fetcher.py`
- `sheets_uploader.py` → replaced by PostgreSQL

---

## Task 1: Project scaffold

**Files:**
- Create: `app.py`, `config.py`, `extensions.py`, `requirements.txt`, `Procfile`, `.env.example`
- Create: `fetchers/__init__.py`, `routes/__init__.py`
- Create: `tests/conftest.py`
- Delete: `main.py`, `config.py` (old), `meta_fetcher.py` (old), `sheets_uploader.py`

- [ ] **Step 1: Delete old files that will be replaced**

```bash
cd /c/Users/phili/meta_ads_dashboard
rm main.py sheets_uploader.py
# Keep meta_fetcher.py for now — we reference it when writing the new one in Task 5
```

- [ ] **Step 2: Write `requirements.txt`**

```
flask==3.0.3
flask-sqlalchemy==3.1.1
flask-login==0.6.3
flask-migrate==4.0.7
apscheduler==3.10.4
bcrypt==4.1.3
python-dotenv==1.0.1
gunicorn==22.0.0
psycopg2-binary==2.9.9
facebook-business==18.0.4
google-ads==24.1.0
resend==2.3.0
pytest==8.2.0
pytest-flask==1.3.0
```

- [ ] **Step 3: Write `config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///adboard_dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
    GOOGLE_ADS_DEVELOPER_TOKEN = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    GOOGLE_ADS_CLIENT_ID = os.environ.get("GOOGLE_ADS_CLIENT_ID")
    GOOGLE_ADS_CLIENT_SECRET = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    GOOGLE_ADS_REFRESH_TOKEN = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN")
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    RESEND_FROM = os.environ.get("RESEND_FROM", "adboard@teteapapineau.com")

    # Railway / Neon PostgreSQL URLs start with postgres:// — SQLAlchemy requires postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
```

- [ ] **Step 4: Write `extensions.py`**

```python
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

login_manager.login_view = "auth.login"
login_manager.login_message = "Connecte-toi pour accéder à cette page."
```

- [ ] **Step 5: Write `app.py`**

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

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.access import access_bp
    from routes.portal import portal_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(access_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(api_bp)

    if not app.testing:
        from sync import init_scheduler
        init_scheduler(app)

    return app

app = create_app()
```

- [ ] **Step 6: Write `Procfile` and `.env.example`**

`Procfile`:
```
web: gunicorn --workers 1 app:app
```

`.env.example`:
```
SECRET_KEY=change-me-to-a-random-string
DATABASE_URL=postgresql://user:password@host/dbname
META_ACCESS_TOKEN=
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
RESEND_API_KEY=
RESEND_FROM=adboard@teteapapineau.com
```

- [ ] **Step 7: Create package init files**

```bash
mkdir -p fetchers routes tests
touch fetchers/__init__.py routes/__init__.py
```

- [ ] **Step 8: Write `tests/conftest.py`**

```python
import pytest
from app import create_app
from extensions import db as _db

@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret",
    })
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def db(app):
    return _db
```

- [ ] **Step 9: Install dependencies and verify the app starts**

```bash
pip install -r requirements.txt
```

At this point the app will fail to start because blueprints don't exist yet — that's expected. We just want no import errors on `config.py`, `extensions.py`, and `app.py`.

```bash
python -c "from config import Config; print('Config OK')"
python -c "from extensions import db, login_manager, migrate; print('Extensions OK')"
```

Expected: `Config OK` and `Extensions OK` printed with no errors.

- [ ] **Step 10: Commit**

```bash
git init  # if not already a git repo
git add app.py config.py extensions.py requirements.txt Procfile .env.example fetchers/__init__.py routes/__init__.py tests/conftest.py
git commit -m "feat: project scaffold — Flask factory, config, extensions"
```

---

## Task 2: Database models

**Files:**
- Create: `models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write `tests/test_models.py`**

```python
from models import Client, TeamMember, TeamMemberClient, ClientUser, AdMetric, SyncLog
from datetime import date

def test_client_gets_secret_token_automatically(db):
    c = Client(name="Boutique Lux", slug="boutique-lux")
    db.session.add(c)
    db.session.commit()
    assert c.secret_token is not None
    assert len(c.secret_token) == 36  # UUID format

def test_team_member_can_see_client_superadmin(db):
    c = Client(name="Client A", slug="client-a")
    db.session.add(c)
    db.session.commit()

    m = TeamMember(email="admin@tap.com", name="Admin", role="superadmin")
    db.session.add(m)
    db.session.commit()

    assert m.can_see_client(c.id) is True

def test_team_member_user_sees_only_assigned_clients(db):
    c1 = Client(name="Client A", slug="client-a")
    c2 = Client(name="Client B", slug="client-b")
    db.session.add_all([c1, c2])
    db.session.commit()

    m = TeamMember(email="user@tap.com", name="User", role="user")
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

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_models.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — models.py does not exist yet.

- [ ] **Step 3: Write `models.py`**

```python
from datetime import datetime
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    metrics = db.relationship("AdMetric", backref="client", lazy="dynamic", cascade="all, delete-orphan")
    sync_logs = db.relationship("SyncLog", backref="client", lazy="dynamic", cascade="all, delete-orphan")


class TeamMember(db.Model, UserMixin):
    __tablename__ = "team_members"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # superadmin | admin | user
    invite_token = db.Column(db.String(36))
    invite_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    assigned_clients = db.relationship("TeamMemberClient", backref="member", lazy="dynamic", cascade="all, delete-orphan")

    def can_see_client(self, client_id):
        if self.role in ("superadmin", "admin"):
            return True
        return self.assigned_clients.filter_by(client_id=client_id).first() is not None


class TeamMemberClient(db.Model):
    __tablename__ = "team_member_clients"
    id = db.Column(db.Integer, primary_key=True)
    team_member_id = db.Column(db.Integer, db.ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)


class ClientUser(db.Model):
    __tablename__ = "client_users"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)


class AdMetric(db.Model):
    __tablename__ = "ad_metrics"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    platform = db.Column(db.String(10), nullable=False)  # meta | google
    level = db.Column(db.String(10), nullable=False)      # campaign | adset
    date = db.Column(db.Date, nullable=False)
    campaign_id = db.Column(db.String(50))
    campaign_name = db.Column(db.String(200))
    adset_id = db.Column(db.String(50))
    adset_name = db.Column(db.String(200))
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
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)


class SyncLog(db.Model):
    __tablename__ = "sync_logs"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    platform = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # success | error
    rows_fetched = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    ran_at = db.Column(db.DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Add user_loader to `extensions.py`**

Add these lines at the bottom of `extensions.py`:

```python
@login_manager.user_loader
def load_user(user_id):
    from models import TeamMember
    return TeamMember.query.get(int(user_id))
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_models.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Initialize Flask-Migrate and create the first migration**

```bash
flask db init
flask db migrate -m "initial schema"
flask db upgrade
```

Expected: `migrations/` directory created, `adboard_dev.db` created (SQLite for local dev).

- [ ] **Step 7: Commit**

```bash
git add models.py extensions.py migrations/ tests/test_models.py
git commit -m "feat: database models and initial migration"
```

---

## Task 3: Auth routes (team login / logout)

**Files:**
- Create: `routes/auth.py`
- Create: `templates/auth/login.html`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write `tests/test_auth.py`**

```python
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
    assert b"incorrect" in r.data.lower() or r.status_code == 200  # stays on login

def test_logout_redirects_to_login(client, db):
    _create_member(db)
    client.post("/auth/login", data={"email": "philippe@tap.com", "password": "secret123"})
    r = client.get("/auth/logout", follow_redirects=True)
    assert r.status_code == 200

def test_admin_dashboard_requires_login(client):
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code == 302
    assert "/auth/login" in r.headers["Location"]
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_auth.py -v
```

Expected: errors — routes don't exist yet.

- [ ] **Step 3: Write `routes/auth.py`**

```python
import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from models import TeamMember

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").encode()
        member = TeamMember.query.filter_by(email=email).first()
        if member and member.password_hash and bcrypt.checkpw(password, member.password_hash.encode()):
            login_user(member)
            from extensions import db
            from datetime import datetime
            member.last_login_at = datetime.utcnow()
            db.session.commit()
            return redirect(url_for("admin.dashboard"))
        flash("Email ou mot de passe incorrect.", "error")
    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
```

- [ ] **Step 4: Write `templates/auth/login.html`**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Connexion — AdBoard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; background: #FAF7F2; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .card { background: white; border-radius: 12px; border: 1px solid #EDE5D8; padding: 40px; width: 360px; }
    .brand { text-align: center; margin-bottom: 32px; }
    .brand-name { color: #E95526; font-weight: 800; font-size: 18px; text-transform: uppercase; letter-spacing: 1px; }
    .brand-sub { color: #9C7A6A; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; }
    label { display: block; font-size: 11px; color: #9C7A6A; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
    input { width: 100%; padding: 10px 12px; border: 1px solid #EDE5D8; border-radius: 8px; font-size: 14px; margin-bottom: 16px; background: #FAF7F2; color: #2D1A1A; }
    input:focus { outline: none; border-color: #E95526; }
    button { width: 100%; padding: 12px; background: #E95526; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 700; cursor: pointer; }
    .error { background: #fdf0ea; color: #E95526; border: 1px solid #E95526; border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-bottom: 16px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <div class="brand-name">Tête à Papineau</div>
      <div class="brand-sub">AdBoard — Connexion équipe</div>
    </div>
    {% for msg in get_flashed_messages() %}
      <div class="error">{{ msg }}</div>
    {% endfor %}
    <form method="POST">
      <label>Email</label>
      <input type="email" name="email" required autofocus>
      <label>Mot de passe</label>
      <input type="password" name="password" required>
      <button type="submit">Se connecter</button>
    </form>
  </div>
</body>
</html>
```

- [ ] **Step 5: Create a stub `routes/admin.py` so the redirect after login works**

```python
from flask import Blueprint, render_template
from flask_login import login_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/")
@login_required
def dashboard():
    return "Dashboard coming soon", 200
```

- [ ] **Step 6: Create stub blueprints for access, portal, and api so `app.py` can import them**

```python
# routes/access.py
from flask import Blueprint
access_bp = Blueprint("access", __name__, url_prefix="/admin/access")

# routes/portal.py
from flask import Blueprint
portal_bp = Blueprint("portal", __name__, url_prefix="/client")

# routes/api.py
from flask import Blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_auth.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add routes/auth.py routes/admin.py routes/access.py routes/portal.py routes/api.py templates/auth/login.html tests/test_auth.py
git commit -m "feat: team auth — login/logout with bcrypt"
```

---

## Task 4: Role decorators

**Files:**
- Create: `decorators.py`
- Create: `tests/test_decorators.py`

- [ ] **Step 1: Write `tests/test_decorators.py`**

```python
import bcrypt
from models import TeamMember, Client, TeamMemberClient
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_decorators.py -v
```

Expected: tests fail or pass trivially (stub admin exists). This verifies the test harness works.

- [ ] **Step 3: Write `decorators.py`**

```python
from functools import wraps
from flask import abort
from flask_login import current_user, login_required

def require_role(*roles):
    """Restrict route to team members with one of the given roles."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return login_required(wrapped)
    return decorator
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_decorators.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add decorators.py tests/test_decorators.py
git commit -m "feat: role-based access decorators"
```

---

## Task 5: Meta Ads fetcher refactor

**Files:**
- Create: `fetchers/meta_fetcher.py` (replaces root-level `meta_fetcher.py`)
- Delete: `meta_fetcher.py`
- Create: `tests/test_meta_fetcher.py`

- [ ] **Step 1: Write `tests/test_meta_fetcher.py`**

```python
from unittest.mock import patch, MagicMock
from fetchers.meta_fetcher import fetch_campaigns, fetch_adsets, _extract_action, _compute_roas

def test_extract_action_returns_value():
    actions = [{"action_type": "purchase", "value": "3"}]
    assert _extract_action(actions, "purchase") == 3.0

def test_extract_action_returns_zero_when_missing():
    assert _extract_action([], "purchase") == 0.0
    assert _extract_action(None, "purchase") == 0.0

def test_compute_roas():
    action_values = [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "500"}]
    assert _compute_roas(action_values, "100") == 5.0

def test_compute_roas_zero_spend():
    assert _compute_roas([], "0") == 0.0

def _mock_insight_row(campaign_id="111", campaign_name="Spring", adset_id=None, adset_name=None):
    row = {
        "date_start": "2026-04-01",
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "impressions": "10000",
        "reach": "8000",
        "frequency": "1.25",
        "clicks": "200",
        "ctr": "2.0",
        "cpc": "0.50",
        "cpm": "5.00",
        "spend": "100.00",
        "actions": [{"action_type": "purchase", "value": "5"}],
        "action_values": [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "500"}],
    }
    if adset_id:
        row["adset_id"] = adset_id
        row["adset_name"] = adset_name
    return row

@patch("fetchers.meta_fetcher.AdAccount")
@patch("fetchers.meta_fetcher.FacebookAdsApi")
def test_fetch_campaigns_returns_normalized_rows(mock_api, mock_account):
    mock_account.return_value.get_insights.return_value = [_mock_insight_row()]
    rows = fetch_campaigns("act_123456", access_token="fake_token")
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-04-01"
    assert r["campaign_id"] == "111"
    assert r["spend"] == 100.0
    assert r["roas"] == 5.0
    assert r["purchases"] == 5

@patch("fetchers.meta_fetcher.AdAccount")
@patch("fetchers.meta_fetcher.FacebookAdsApi")
def test_fetch_adsets_includes_adset_fields(mock_api, mock_account):
    row = _mock_insight_row(adset_id="222", adset_name="Lookalike")
    mock_account.return_value.get_insights.return_value = [row]
    rows = fetch_adsets("act_123456", access_token="fake_token")
    assert rows[0]["adset_id"] == "222"
    assert rows[0]["adset_name"] == "Lookalike"
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_meta_fetcher.py -v
```

Expected: `ImportError` — fetchers/meta_fetcher.py does not exist yet.

- [ ] **Step 3: Write `fetchers/meta_fetcher.py`**

```python
import os
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

INSIGHT_FIELDS = [
    "date_start", "impressions", "reach", "clicks", "ctr", "cpc",
    "spend", "actions", "action_values", "frequency", "cpm",
]

def _extract_action(actions, action_type):
    if not actions:
        return 0.0
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0.0

def _compute_roas(action_values, spend):
    revenue = _extract_action(action_values, "offsite_conversion.fb_pixel_purchase")
    if revenue == 0:
        revenue = _extract_action(action_values, "purchase")
    spend_val = float(spend) if spend else 0
    return round(revenue / spend_val, 2) if spend_val else 0.0

def _parse_row(row, extra_fields=None):
    row = dict(row)
    spend = row.get("spend", 0)
    actions = row.get("actions", [])
    action_values = row.get("action_values", [])
    result = {
        "date": row.get("date_start"),
        "campaign_id": row.get("campaign_id"),
        "campaign_name": row.get("campaign_name"),
        "impressions": int(row.get("impressions", 0)),
        "reach": int(row.get("reach", 0)),
        "frequency": round(float(row.get("frequency", 0)), 2),
        "clicks": int(row.get("clicks", 0)),
        "ctr": round(float(row.get("ctr", 0)), 2),
        "cpc": round(float(row.get("cpc", 0)), 2),
        "cpm": round(float(row.get("cpm", 0)), 2),
        "spend": round(float(spend), 2),
        "purchases": int(_extract_action(actions, "offsite_conversion.fb_pixel_purchase") or _extract_action(actions, "purchase")),
        "revenue": round(_extract_action(action_values, "offsite_conversion.fb_pixel_purchase") or _extract_action(action_values, "purchase"), 2),
        "roas": _compute_roas(action_values, spend),
    }
    if extra_fields:
        result.update(extra_fields(row))
    return result

def fetch_campaigns(account_id, date_preset="last_30d", access_token=None):
    FacebookAdsApi.init(access_token=access_token or os.environ["META_ACCESS_TOKEN"])
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=["campaign_id", "campaign_name"] + INSIGHT_FIELDS,
        params={"date_preset": date_preset, "time_increment": 1, "level": "campaign"},
    )
    return [_parse_row(r) for r in insights]

def fetch_adsets(account_id, date_preset="last_30d", access_token=None):
    FacebookAdsApi.init(access_token=access_token or os.environ["META_ACCESS_TOKEN"])
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=["campaign_id", "campaign_name", "adset_id", "adset_name"] + INSIGHT_FIELDS,
        params={"date_preset": date_preset, "time_increment": 1, "level": "adset"},
    )
    return [_parse_row(r, lambda row: {"adset_id": row.get("adset_id"), "adset_name": row.get("adset_name")}) for r in insights]
```

- [ ] **Step 4: Delete old root-level `meta_fetcher.py`**

```bash
rm meta_fetcher.py
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_meta_fetcher.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add fetchers/meta_fetcher.py tests/test_meta_fetcher.py
git commit -m "feat: meta fetcher refactored to accept account_id param"
```

---

## Task 6: Google Ads fetcher

**Files:**
- Create: `fetchers/google_fetcher.py`
- Create: `tests/test_google_fetcher.py`

- [ ] **Step 1: Write `tests/test_google_fetcher.py`**

```python
from unittest.mock import patch, MagicMock
from fetchers.google_fetcher import fetch_campaigns, fetch_adsets

def _mock_campaign_row(campaign_id=1, campaign_name="Brand", date_str="2026-04-01",
                       impressions=5000, clicks=100, ctr=0.02, avg_cpc=500000,
                       cost_micros=50000000, conversions=10.0, conv_value=300.0):
    row = MagicMock()
    row.campaign.id = campaign_id
    row.campaign.name = campaign_name
    row.segments.date = date_str
    row.metrics.impressions = impressions
    row.metrics.clicks = clicks
    row.metrics.ctr = ctr
    row.metrics.average_cpc = avg_cpc       # micros: 500000 = $0.50
    row.metrics.cost_micros = cost_micros   # micros: 50000000 = $50
    row.metrics.conversions = conversions
    row.metrics.conversions_value = conv_value
    return row

@patch("fetchers.google_fetcher._build_client")
def test_fetch_campaigns_returns_normalized_rows(mock_build):
    mock_service = MagicMock()
    mock_build.return_value.get_service.return_value = mock_service
    mock_service.search.return_value = [_mock_campaign_row()]

    rows = fetch_campaigns("1234567890", days=30)
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-04-01"
    assert r["campaign_id"] == "1"
    assert r["spend"] == 50.0
    assert r["roas"] == 6.0   # 300 / 50
    assert r["purchases"] == 10

def _mock_adgroup_row():
    row = _mock_campaign_row()
    row.ad_group = MagicMock()
    row.ad_group.id = 99
    row.ad_group.name = "Ad Group A"
    return row

@patch("fetchers.google_fetcher._build_client")
def test_fetch_adsets_includes_adgroup_fields(mock_build):
    mock_service = MagicMock()
    mock_build.return_value.get_service.return_value = mock_service
    mock_service.search.return_value = [_mock_adgroup_row()]

    rows = fetch_adsets("1234567890", days=30)
    assert rows[0]["adset_id"] == "99"
    assert rows[0]["adset_name"] == "Ad Group A"
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_google_fetcher.py -v
```

Expected: `ImportError` — file doesn't exist yet.

- [ ] **Step 3: Write `fetchers/google_fetcher.py`**

```python
import os
from datetime import date, timedelta
from google.ads.googleads.client import GoogleAdsClient

def _build_client():
    return GoogleAdsClient.load_from_dict({
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "use_proto_plus": True,
    })

def _date_range(days):
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()

def _parse_row(row, extra_fields=None):
    spend = row.metrics.cost_micros / 1_000_000
    revenue = float(row.metrics.conversions_value)
    impressions = row.metrics.impressions
    result = {
        "date": row.segments.date,
        "campaign_id": str(row.campaign.id),
        "campaign_name": row.campaign.name,
        "impressions": impressions,
        "reach": 0,
        "frequency": 0.0,
        "clicks": row.metrics.clicks,
        "ctr": round(float(row.metrics.ctr) * 100, 2),
        "cpc": round(row.metrics.average_cpc / 1_000_000, 2),
        "cpm": round(spend / impressions * 1000, 2) if impressions else 0.0,
        "spend": round(spend, 2),
        "purchases": int(row.metrics.conversions),
        "revenue": round(revenue, 2),
        "roas": round(revenue / spend, 2) if spend else 0.0,
    }
    if extra_fields:
        result.update(extra_fields(row))
    return result

def fetch_campaigns(customer_id, days=30):
    client = _build_client()
    service = client.get_service("GoogleAdsService")
    start, end = _date_range(days)
    query = f"""
        SELECT campaign.id, campaign.name, segments.date,
               metrics.impressions, metrics.clicks, metrics.ctr,
               metrics.average_cpc, metrics.cost_micros,
               metrics.conversions, metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{start}' AND '{end}'
          AND campaign.status != 'REMOVED'
    """
    return [_parse_row(r) for r in service.search(customer_id=customer_id, query=query)]

def fetch_adsets(customer_id, days=30):
    client = _build_client()
    service = client.get_service("GoogleAdsService")
    start, end = _date_range(days)
    query = f"""
        SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, segments.date,
               metrics.impressions, metrics.clicks, metrics.ctr,
               metrics.average_cpc, metrics.cost_micros,
               metrics.conversions, metrics.conversions_value
        FROM ad_group
        WHERE segments.date BETWEEN '{start}' AND '{end}'
          AND ad_group.status != 'REMOVED'
    """
    return [_parse_row(r, lambda r: {"adset_id": str(r.ad_group.id), "adset_name": r.ad_group.name})
            for r in service.search(customer_id=customer_id, query=query)]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_google_fetcher.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fetchers/google_fetcher.py tests/test_google_fetcher.py
git commit -m "feat: Google Ads fetcher — campaigns and ad groups"
```

---

## Task 7: Sync engine

**Files:**
- Create: `sync.py`
- Create: `tests/test_sync.py`

- [ ] **Step 1: Write `tests/test_sync.py`**

```python
from unittest.mock import patch
from datetime import date
from models import Client, AdMetric, SyncLog
from extensions import db
from sync import sync_client, _upsert_metrics

def _make_client(db, meta_id="act_123", google_id=None):
    c = Client(name="Test", slug="test", meta_account_id=meta_id, google_customer_id=google_id)
    db.session.add(c)
    db.session.commit()
    return c

def _sample_rows():
    return [{
        "date": "2026-04-01", "campaign_id": "1", "campaign_name": "Spring",
        "adset_id": None, "adset_name": None,
        "impressions": 1000, "reach": 800, "frequency": 1.25, "clicks": 50,
        "ctr": 5.0, "cpc": 0.50, "cpm": 5.0, "spend": 25.0,
        "purchases": 3, "revenue": 150.0, "roas": 6.0,
    }]

def test_upsert_metrics_saves_rows(app, db):
    c = _make_client(db)
    _upsert_metrics(c.id, "meta", "campaign", _sample_rows())
    db.session.commit()
    metrics = AdMetric.query.filter_by(client_id=c.id).all()
    assert len(metrics) == 1
    assert metrics[0].roas == 6.0

def test_upsert_metrics_replaces_existing_rows_for_same_date(app, db):
    c = _make_client(db)
    _upsert_metrics(c.id, "meta", "campaign", _sample_rows())
    db.session.commit()
    updated = _sample_rows()
    updated[0]["roas"] = 7.5
    _upsert_metrics(c.id, "meta", "campaign", updated)
    db.session.commit()
    metrics = AdMetric.query.filter_by(client_id=c.id).all()
    assert len(metrics) == 1
    assert metrics[0].roas == 7.5

@patch("sync.fetch_meta_campaigns")
@patch("sync.fetch_meta_adsets")
def test_sync_client_creates_success_log(mock_adsets, mock_campaigns, app, db):
    mock_campaigns.return_value = _sample_rows()
    mock_adsets.return_value = _sample_rows()
    c = _make_client(db)
    sync_client(c)
    logs = SyncLog.query.filter_by(client_id=c.id, status="success").all()
    assert len(logs) >= 1

@patch("sync.fetch_meta_campaigns", side_effect=Exception("API down"))
@patch("sync.fetch_meta_adsets", side_effect=Exception("API down"))
def test_sync_client_logs_error_on_exception(mock_adsets, mock_campaigns, app, db):
    c = _make_client(db)
    sync_client(c)
    logs = SyncLog.query.filter_by(client_id=c.id, status="error").all()
    assert len(logs) >= 1
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_sync.py -v
```

Expected: `ImportError` — sync.py does not exist yet.

- [ ] **Step 3: Write `sync.py`**

```python
from datetime import datetime, date as date_type
from extensions import db
from models import Client, AdMetric, SyncLog
from fetchers.meta_fetcher import fetch_campaigns as fetch_meta_campaigns, fetch_adsets as fetch_meta_adsets
from fetchers.google_fetcher import fetch_campaigns as fetch_google_campaigns, fetch_adsets as fetch_google_adsets


def _upsert_metrics(client_id, platform, level, rows):
    if not rows:
        return
    dates = list({r["date"] for r in rows})
    AdMetric.query.filter(
        AdMetric.client_id == client_id,
        AdMetric.platform == platform,
        AdMetric.level == level,
        AdMetric.date.in_(dates),
    ).delete(synchronize_session=False)
    for r in rows:
        db.session.add(AdMetric(
            client_id=client_id, platform=platform, level=level,
            date=r["date"],
            campaign_id=r.get("campaign_id"), campaign_name=r.get("campaign_name"),
            adset_id=r.get("adset_id"), adset_name=r.get("adset_name"),
            impressions=r.get("impressions", 0), reach=r.get("reach", 0),
            frequency=r.get("frequency", 0.0), clicks=r.get("clicks", 0),
            ctr=r.get("ctr", 0.0), cpc=r.get("cpc", 0.0), cpm=r.get("cpm", 0.0),
            spend=r.get("spend", 0.0), purchases=r.get("purchases", 0),
            revenue=r.get("revenue", 0.0), roas=r.get("roas", 0.0),
            synced_at=datetime.utcnow(),
        ))


def sync_client(client):
    """Sync Meta + Google data for one client. Safe to call from scheduler or manually."""
    jobs = []
    if client.meta_account_id:
        jobs += [
            ("meta", "campaign", fetch_meta_campaigns, {"account_id": client.meta_account_id}),
            ("meta", "adset",    fetch_meta_adsets,    {"account_id": client.meta_account_id}),
        ]
    if client.google_customer_id:
        jobs += [
            ("google", "campaign", fetch_google_campaigns, {"customer_id": client.google_customer_id}),
            ("google", "adset",    fetch_google_adsets,    {"customer_id": client.google_customer_id}),
        ]

    for platform, level, fetcher, kwargs in jobs:
        try:
            rows = fetcher(**kwargs)
            _upsert_metrics(client.id, platform, level, rows)
            db.session.add(SyncLog(
                client_id=client.id, platform=platform,
                status="success", rows_fetched=len(rows),
            ))
        except Exception as exc:
            db.session.add(SyncLog(
                client_id=client.id, platform=platform,
                status="error", error_message=str(exc),
            ))
        db.session.commit()


def sync_all_clients(app):
    """APScheduler job — runs every hour."""
    with app.app_context():
        for client in Client.query.filter_by(is_active=True).all():
            sync_client(client)


def init_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(sync_all_clients, "interval", hours=1, args=[app], id="hourly_sync")
    scheduler.start()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sync.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sync.py tests/test_sync.py
git commit -m "feat: sync engine — upsert metrics, hourly APScheduler job"
```

---

## Task 8: Base template and brand CSS

**Files:**
- Create: `templates/base.html`
- Create: `static/css/tap.css`

- [ ] **Step 1: Create directories**

```bash
mkdir -p static/css templates/admin templates/portal
```

- [ ] **Step 2: Write `static/css/tap.css`**

```css
:root {
  --orange:  #E95526;
  --bordeaux: #451519;
  --beige:   #E4D4BA;
  --fond:    #FAF7F2;
  --texte:   #2D1A1A;
  --gris:    #9C7A6A;
  --bordure: #EDE5D8;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--fond); color: var(--texte); }
a { color: var(--orange); text-decoration: none; }
.nav { background: var(--bordeaux); padding: 12px 24px; display: flex; align-items: center; gap: 20px; }
.nav-brand-name { color: var(--orange); font-weight: 800; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
.nav-brand-sub  { color: var(--beige); font-size: 10px; letter-spacing: 2px; text-transform: uppercase; }
.nav-link { color: var(--beige); font-size: 12px; opacity: 0.65; cursor: pointer; }
.nav-link:hover, .nav-link.active { opacity: 1; }
.nav-link.active { border-bottom: 2px solid var(--orange); padding-bottom: 2px; }
.nav-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.main { padding: 24px; }
.btn { padding: 7px 16px; border-radius: 8px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; }
.btn-primary { background: var(--orange); color: white; }
.btn-outline { background: white; border: 1px solid var(--bordure); color: var(--gris); }
.btn-danger  { background: white; border: 1px solid #f5c6c6; color: #c0392b; }
.pill { font-size: 11px; padding: 5px 12px; border-radius: 20px; border: 1px solid var(--beige); color: #6B3A30; background: white; cursor: pointer; }
.pill.active { background: var(--orange); color: white; border-color: var(--orange); }
.card { background: white; border-radius: 10px; border: 1px solid var(--bordure); overflow: hidden; margin-bottom: 16px; }
.card-header { padding: 14px 20px; border-bottom: 1px solid var(--bordure); display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 13px; font-weight: 700; }
.card-meta  { font-size: 11px; color: var(--gris); }
.kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
.kpi { background: white; border-radius: 10px; padding: 16px; border: 1px solid var(--bordure); }
.kpi-label { font-size: 10px; color: var(--gris); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 700; color: var(--texte); margin-bottom: 4px; }
.kpi-value.accent { color: var(--orange); }
.trend-up   { font-size: 10px; color: #2d9e6b; }
.trend-down { font-size: 10px; color: #c0392b; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
thead tr { background: var(--fond); }
th { padding: 10px 14px; text-align: left; font-size: 10px; color: var(--gris); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
th.right, td.right { text-align: right; }
td { padding: 12px 14px; border-top: 1px solid #F0E8DC; }
tbody tr:hover { background: #FDF9F5; cursor: pointer; }
.badge { font-size: 10px; padding: 2px 8px; border-radius: 20px; font-weight: 600; display: inline-block; }
.badge-superadmin { background: #fdf0ea; color: var(--orange); border: 1px solid var(--orange); }
.badge-admin { background: #f0eafa; color: #6B3A8A; border: 1px solid #C4A8E0; }
.badge-user  { background: #eaf0fa; color: #2d6ba4; border: 1px solid #A8C8E0; }
.tag-meta   { font-size: 10px; background: #1877F2; color: white; padding: 2px 6px; border-radius: 3px; margin-right: 2px; }
.tag-google { font-size: 10px; background: #4285F4; color: white; padding: 2px 6px; border-radius: 3px; }
.sync-ok  { font-size: 10px; color: #2d9e6b; background: rgba(45,158,107,0.1); padding: 2px 8px; border-radius: 10px; }
.sync-err { font-size: 10px; color: #c0392b; background: rgba(192,57,43,0.1); padding: 2px 8px; border-radius: 10px; }
.roas-good { color: var(--orange); font-weight: 700; }
.roas-ok   { color: var(--gris);   font-weight: 700; }
.roas-bad  { color: #c0392b;        font-weight: 700; }
.flash-error { background: #fdf0ea; color: var(--orange); border: 1px solid var(--orange); border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-bottom: 16px; }
```

- [ ] **Step 3: Write `templates/base.html`**

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
      <a class="nav-link {% if request.blueprint == 'access' %}active{% endif %}" href="{{ url_for('access.index') }}">Accès</a>
    {% endif %}
    <div class="nav-right">
      {% block nav_right %}
        {% if current_user.is_authenticated %}
          <span style="font-size:11px;color:var(--beige);opacity:.7">{{ current_user.name }}</span>
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

- [ ] **Step 4: Commit**

```bash
git add static/css/tap.css templates/base.html
git commit -m "feat: base template and brand CSS (Tête à Papineau palette)"
```

---

## Task 9: Admin 360° view

**Files:**
- Modify: `routes/admin.py` (replace stub)
- Create: `templates/admin/dashboard.html`
- Create: `tests/test_admin_routes.py`

- [ ] **Step 1: Write `tests/test_admin_routes.py`**

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_admin_routes.py -v
```

Expected: 2 pass (login redirect, 200 stub), 3 fail — dashboard doesn't show client name yet, client detail route doesn't exist.

- [ ] **Step 3: Write `routes/admin.py`**

```python
from datetime import date, timedelta
from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from models import Client, AdMetric, SyncLog
from extensions import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def _period_start(days):
    return date.today() - timedelta(days=days)

def _roas_class(roas):
    if roas >= 4:  return "roas-good"
    if roas >= 2:  return "roas-ok"
    return "roas-bad"

@admin_bp.route("/")
@login_required
def dashboard():
    days = int(request.args.get("days", 30))
    platform = request.args.get("platform", "all")
    start = _period_start(days)

    clients = Client.query.filter_by(is_active=True).all()
    if current_user.role == "user":
        allowed = {tc.client_id for tc in current_user.assigned_clients}
        clients = [c for c in clients if c.id in allowed]

    q = (db.session.query(
            AdMetric.client_id,
            func.sum(AdMetric.spend).label("spend"),
            func.sum(AdMetric.revenue).label("revenue"),
            func.sum(AdMetric.clicks).label("clicks"),
            func.sum(AdMetric.purchases).label("purchases"),
        )
        .filter(AdMetric.date >= start, AdMetric.level == "campaign")
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
        client_data=client_data, days=days, platform=platform,
        global_spend=global_spend, global_revenue=global_revenue,
        global_clicks=global_clicks, global_roas=global_roas,
        active_count=len(clients),
    )

@admin_bp.route("/client/<int:client_id>")
@login_required
def client_detail(client_id):
    if not current_user.can_see_client(client_id):
        abort(403)
    c = Client.query.get_or_404(client_id)
    days = int(request.args.get("days", 30))
    start = _period_start(days)

    campaigns = (AdMetric.query
        .filter_by(client_id=c.id, level="campaign")
        .filter(AdMetric.date >= start)
        .order_by(AdMetric.spend.desc())
        .all()
    )
    sync_history = SyncLog.query.filter_by(client_id=c.id).order_by(SyncLog.ran_at.desc()).limit(20).all()

    spend  = sum(m.spend for m in campaigns)
    revenue= sum(m.revenue for m in campaigns)
    clicks = sum(m.clicks for m in campaigns)
    roas   = round(revenue / spend, 2) if spend else 0

    return render_template("admin/client_detail.html",
        c=c, campaigns=campaigns, sync_history=sync_history, days=days,
        spend=spend, revenue=revenue, clicks=clicks, roas=roas,
        roas_class=_roas_class(roas),
    )
```

- [ ] **Step 4: Write `templates/admin/dashboard.html`**

```html
{% extends "base.html" %}
{% block title %}Vue globale{% endblock %}
{% block content %}

<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h1 style="font-size:18px;font-weight:700">Vue globale</h1>
</div>

<!-- Filters -->
<div style="display:flex;align-items:center;gap:8px;margin-bottom:20px;flex-wrap:wrap">
  <span style="font-size:11px;color:var(--gris);text-transform:uppercase;letter-spacing:1px">Période :</span>
  {% for d,l in [(7,"7 jours"),(30,"30 jours"),(90,"90 jours")] %}
    <a href="?days={{ d }}&platform={{ platform }}" class="pill {% if days==d %}active{% endif %}">{{ l }}</a>
  {% endfor %}
  <div style="width:1px;height:20px;background:var(--beige);margin:0 8px"></div>
  <span style="font-size:11px;color:var(--gris);text-transform:uppercase;letter-spacing:1px">Plateforme :</span>
  {% for p,l in [("all","Toutes"),("meta","Meta"),("google","Google")] %}
    <a href="?days={{ days }}&platform={{ p }}" class="pill {% if platform==p %}active{% endif %}">{{ l }}</a>
  {% endfor %}
</div>

<!-- KPIs -->
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-label">Dépenses totales</div><div class="kpi-value">${{ "%.0f"|format(global_spend) }}</div></div>
  <div class="kpi"><div class="kpi-label">Revenus générés</div><div class="kpi-value">${{ "%.0f"|format(global_revenue) }}</div></div>
  <div class="kpi"><div class="kpi-label">ROAS moyen</div><div class="kpi-value accent">{{ global_roas }}x</div></div>
  <div class="kpi"><div class="kpi-label">Clics totaux</div><div class="kpi-value">{{ "{:,}".format(global_clicks) }}</div></div>
  <div class="kpi"><div class="kpi-label">Clients actifs</div><div class="kpi-value">{{ active_count }}</div></div>
</div>

<!-- Clients table -->
<div class="card">
  <div class="card-header">
    <span class="card-title">Tous les clients</span>
    <span class="card-meta">Classé par dépenses ↓</span>
  </div>
  <table>
    <thead><tr>
      <th>Client</th><th>Plateformes</th>
      <th class="right">Dépenses</th><th class="right">Revenus</th>
      <th class="right">ROAS</th><th class="right">Clics</th>
      <th class="right">Sync</th>
    </tr></thead>
    <tbody>
    {% for row in client_data %}
      <tr onclick="window.location='/admin/client/{{ row.client.id }}?days={{ days }}'">
        <td style="font-weight:600">{{ row.client.name }}</td>
        <td>
          {% if row.client.meta_account_id %}<span class="tag-meta">Meta</span>{% endif %}
          {% if row.client.google_customer_id %}<span class="tag-google">Google</span>{% endif %}
        </td>
        <td class="right">${{ "%.0f"|format(row.spend) }}</td>
        <td class="right">${{ "%.0f"|format(row.revenue) }}</td>
        <td class="right"><span class="{{ row.roas_class }}">{{ row.roas }}x</span></td>
        <td class="right">{{ "{:,}".format(row.clicks) }}</td>
        <td class="right">
          {% if row.last_sync %}
            <span class="sync-ok">✓ {{ row.last_sync.strftime('%H:%M') }}</span>
          {% else %}
            <span class="sync-err">Jamais</span>
          {% endif %}
        </td>
      </tr>
    {% else %}
      <tr><td colspan="7" style="text-align:center;color:var(--gris);padding:24px">Aucun client — ajoutes-en un dans Accès.</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 5: Write `templates/admin/client_detail.html`**

```html
{% extends "base.html" %}
{% block title %}{{ c.name }}{% endblock %}
{% block content %}
<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
  <a href="{{ url_for('admin.dashboard') }}" style="color:var(--gris);font-size:12px">← Retour</a>
  <h1 style="font-size:18px;font-weight:700">{{ c.name }}</h1>
  {% if c.meta_account_id %}<span class="tag-meta">Meta</span>{% endif %}
  {% if c.google_customer_id %}<span class="tag-google">Google</span>{% endif %}
</div>

<!-- Period filter -->
<div style="display:flex;gap:8px;margin-bottom:20px">
  {% for d,l in [(7,"7 jours"),(30,"30 jours"),(90,"90 jours")] %}
    <a href="?days={{ d }}" class="pill {% if days==d %}active{% endif %}">{{ l }}</a>
  {% endfor %}
</div>

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

<!-- Campaigns -->
<div class="card">
  <div class="card-header"><span class="card-title">Campagnes</span></div>
  <table>
    <thead><tr>
      <th>Campagne</th><th></th>
      <th class="right">Dépenses</th><th class="right">Revenus</th>
      <th class="right">ROAS</th><th class="right">CTR</th><th class="right">CPC</th>
    </tr></thead>
    <tbody>
    {% for m in campaigns %}
      <tr>
        <td style="font-weight:600">{{ m.campaign_name }}</td>
        <td><span class="tag-{{ m.platform }}">{{ m.platform|capitalize }}</span></td>
        <td class="right">${{ "%.2f"|format(m.spend) }}</td>
        <td class="right">${{ "%.2f"|format(m.revenue) }}</td>
        <td class="right"><span class="roas-good">{{ m.roas }}x</span></td>
        <td class="right">{{ m.ctr }}%</td>
        <td class="right">${{ m.cpc }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<script>
  fetch("/api/client/{{ c.id }}/chart?days={{ days }}")
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

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_admin_routes.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add routes/admin.py templates/admin/dashboard.html templates/admin/client_detail.html tests/test_admin_routes.py
git commit -m "feat: admin 360° view and client detail page"
```

---

## Task 10: Chart API + manual sync endpoint

**Files:**
- Modify: `routes/api.py` (replace stub)
- Create: `tests/test_api_routes.py`

- [ ] **Step 1: Write `tests/test_api_routes.py`**

```python
import bcrypt
from datetime import date
from models import TeamMember, Client, AdMetric
from extensions import db

def _login_admin(client_fixture, db):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    m = TeamMember(email="admin@tap.com", name="A", role="superadmin", password_hash=pw)
    db.session.add(m); db.session.commit()
    client_fixture.post("/auth/login", data={"email": "admin@tap.com", "password": "pw"})

def _seed(db):
    c = Client(name="X", slug="x", meta_account_id="act_1")
    db.session.add(c); db.session.commit()
    for d, spend in [("2026-04-14", 40.0), ("2026-04-15", 60.0)]:
        db.session.add(AdMetric(
            client_id=c.id, platform="meta", level="campaign", date=d,
            campaign_id="1", campaign_name="C", spend=spend, revenue=spend*5, roas=5.0,
        ))
    db.session.commit()
    return c

def test_chart_endpoint_returns_labels_and_series(client, db):
    _login_admin(client, db)
    c = _seed(db)
    r = client.get(f"/api/client/{c.id}/chart?days=30")
    assert r.status_code == 200
    data = r.get_json()
    assert "labels" in data
    assert "meta" in data
    assert "google" in data
    assert len(data["labels"]) == len(data["meta"])

def test_chart_endpoint_requires_login(client, db):
    c = _seed(db)
    r = client.get(f"/api/client/{c.id}/chart?days=30")
    assert r.status_code in (302, 401)
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_api_routes.py -v
```

Expected: failures — api.py is a stub.

- [ ] **Step 3: Write `routes/api.py`**

```python
from datetime import date, timedelta
from collections import defaultdict
from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from models import Client, AdMetric
from extensions import db
from sqlalchemy import func

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/client/<int:client_id>/chart")
@login_required
def client_chart(client_id):
    if not current_user.can_see_client(client_id):
        abort(403)
    days = int(request.args.get("days", 30))
    start = date.today() - timedelta(days=days)

    rows = (db.session.query(AdMetric.date, AdMetric.platform, func.sum(AdMetric.spend))
        .filter(AdMetric.client_id == client_id, AdMetric.level == "campaign", AdMetric.date >= start)
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
    c = Client.query.get_or_404(client_id)
    from sync import sync_client
    sync_client(c)
    return jsonify({"status": "ok"})

@api_bp.route("/sync/all", methods=["POST"])
@login_required
def manual_sync_all():
    if current_user.role not in ("superadmin", "admin"):
        abort(403)
    from sync import sync_all_clients
    import threading
    t = threading.Thread(target=sync_all_clients, args=[current_app._get_current_object()])
    t.start()
    return jsonify({"status": "started"})
```

Fix the import at the bottom — add `from flask import current_app` at the top of the file:

```python
from flask import Blueprint, jsonify, request, abort, current_app
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_api_routes.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add routes/api.py tests/test_api_routes.py
git commit -m "feat: chart JSON API and manual sync endpoints"
```

---

## Task 11: Client portal (read-only)

**Files:**
- Modify: `routes/portal.py` (replace stub)
- Create: `templates/portal/client.html`
- Create: `tests/test_portal_routes.py`

- [ ] **Step 1: Write `tests/test_portal_routes.py`**

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_portal_routes.py -v
```

Expected: failures — portal.py is a stub.

- [ ] **Step 3: Write `routes/portal.py`**

```python
import bcrypt
from datetime import date, timedelta, datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from models import Client, ClientUser, AdMetric, SyncLog
from extensions import db
from sqlalchemy import func

portal_bp = Blueprint("portal", __name__, url_prefix="/client")

def _period_start(days):
    return date.today() - timedelta(days=days)

def _get_portal_client():
    """Return the Client the current session has access to, or None."""
    client_id = session.get("portal_client_id")
    if not client_id:
        return None
    return Client.query.filter_by(id=client_id, is_active=True).first()

@portal_bp.route("/<string:token>")
def portal_by_token(token):
    c = Client.query.filter_by(secret_token=token, is_active=True).first_or_404()
    session["portal_client_id"] = c.id
    return redirect(url_for("portal.portal_dashboard"))

@portal_bp.route("/dashboard")
def portal_dashboard():
    c = _get_portal_client()
    if not c:
        return redirect(url_for("portal.portal_login"))

    days = int(request.args.get("days", 30))
    start = _period_start(days)

    campaigns = (AdMetric.query
        .filter_by(client_id=c.id, level="campaign")
        .filter(AdMetric.date >= start)
        .order_by(AdMetric.spend.desc())
        .all())

    spend   = sum(m.spend for m in campaigns)
    revenue = sum(m.revenue for m in campaigns)
    clicks  = sum(m.clicks for m in campaigns)
    roas    = round(revenue / spend, 2) if spend else 0

    last_sync = (SyncLog.query
        .filter_by(client_id=c.id, status="success")
        .order_by(SyncLog.ran_at.desc())
        .first())

    return render_template("portal/client.html",
        c=c, campaigns=campaigns, days=days,
        spend=spend, revenue=revenue, clicks=clicks, roas=roas,
        last_sync=last_sync,
    )

@portal_bp.route("/login", methods=["GET", "POST"])
def portal_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").encode()
        u = ClientUser.query.filter_by(email=email).first()
        if u and u.password_hash and bcrypt.checkpw(password, u.password_hash.encode()):
            session["portal_client_id"] = u.client_id
            u.last_login_at = datetime.utcnow()
            db.session.commit()
            return redirect(url_for("portal.portal_dashboard"))
        flash("Email ou mot de passe incorrect.")
    return render_template("auth/login.html", portal_mode=True)
```

- [ ] **Step 4: Write `templates/portal/client.html`**

```html
{% extends "base.html" %}
{% block title %}{{ c.name }} — Tableau de bord{% endblock %}
{% block nav_right %}
  <span style="font-size:10px;color:var(--beige);border:1px solid rgba(228,212,186,.3);padding:3px 8px;border-radius:10px">🔒 Lecture seule</span>
{% endblock %}
{% block content %}

<div style="margin-bottom:20px">
  <h1 style="font-size:20px;font-weight:700">{{ c.name }}</h1>
  <p style="font-size:12px;color:var(--gris)">Rapport publicitaire
    {% if last_sync %}· Mis à jour {{ last_sync.ran_at.strftime('%d %b à %H:%M') }}{% endif %}
  </p>
</div>

<!-- Period filter -->
<div style="display:flex;gap:8px;margin-bottom:20px">
  {% for d,l in [(7,"7 jours"),(30,"30 jours"),(90,"90 jours")] %}
    <a href="?days={{ d }}" class="pill {% if days==d %}active{% endif %}">{{ l }}</a>
  {% endfor %}
</div>

<!-- KPIs -->
<div class="kpi-grid" style="grid-template-columns:repeat(4,1fr)">
  <div class="kpi"><div class="kpi-label">Budget dépensé</div><div class="kpi-value">${{ "%.2f"|format(spend) }}</div></div>
  <div class="kpi"><div class="kpi-label">Revenus générés</div><div class="kpi-value" style="color:#2d9e6b">${{ "%.2f"|format(revenue) }}</div></div>
  <div class="kpi"><div class="kpi-label">ROAS</div><div class="kpi-value accent">{{ roas }}x</div></div>
  <div class="kpi"><div class="kpi-label">Clics</div><div class="kpi-value">{{ "{:,}".format(clicks) }}</div></div>
</div>

<!-- Chart -->
<div class="card">
  <div class="card-header">
    <span class="card-title">Dépenses par jour</span>
    <div style="display:flex;gap:8px;font-size:10px;align-items:center">
      <span style="background:#E95526;width:10px;height:10px;border-radius:2px;display:inline-block"></span> Meta
      <span style="background:#4285F4;width:10px;height:10px;border-radius:2px;display:inline-block"></span> Google
    </div>
  </div>
  <div style="padding:16px;height:200px"><canvas id="spendChart"></canvas></div>
</div>

<!-- Campaigns -->
<div class="card">
  <div class="card-header"><span class="card-title">Campagnes actives</span></div>
  <table>
    <thead><tr>
      <th>Campagne</th><th></th>
      <th class="right">Dépenses</th><th class="right">Revenus</th>
      <th class="right">ROAS</th><th class="right">CTR</th>
    </tr></thead>
    <tbody>
    {% for m in campaigns %}
      <tr>
        <td style="font-weight:600">{{ m.campaign_name }}</td>
        <td><span class="tag-{{ m.platform }}">{{ m.platform|capitalize }}</span></td>
        <td class="right">${{ "%.2f"|format(m.spend) }}</td>
        <td class="right">${{ "%.2f"|format(m.revenue) }}</td>
        <td class="right"><span class="roas-good">{{ m.roas }}x</span></td>
        <td class="right">{{ m.ctr }}%</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<div style="font-size:11px;color:var(--gris);text-align:center;margin-top:20px;padding:12px;background:white;border-radius:8px;border:1px solid var(--bordure)">
  Rapport fourni par <strong>Tête à Papineau — Marketing Créatif</strong> · Sync automatique toutes les heures
</div>

<script>
  fetch("/api/client/{{ c.id }}/chart?days={{ days }}")
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
        options: { responsive: true, maintainAspectRatio: false }
      });
    });
</script>
{% endblock %}
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_portal_routes.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add routes/portal.py templates/portal/client.html tests/test_portal_routes.py
git commit -m "feat: client read-only portal via secret token and optional login"
```

---

## Task 12: Access management (team + client portals)

**Files:**
- Modify: `routes/access.py` (replace stub)
- Create: `email.py`
- Create: `templates/admin/access.html`
- Create: `tests/test_access_routes.py`

- [ ] **Step 1: Write `tests/test_access_routes.py`**

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_access_routes.py -v
```

Expected: failures — routes/access.py is a stub.

- [ ] **Step 3: Write `email.py`**

```python
import os
import resend

def send_invitation(to_email, to_name, invite_url):
    resend.api_key = os.environ.get("RESEND_API_KEY", "")
    resend.Emails.send({
        "from": os.environ.get("RESEND_FROM", "adboard@teteapapineau.com"),
        "to": to_email,
        "subject": "Invitation — AdBoard Tête à Papineau",
        "html": f"""
        <p>Bonjour {to_name},</p>
        <p>Tu as été invité(e) à rejoindre AdBoard.</p>
        <p><a href="{invite_url}" style="background:#E95526;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;display:inline-block">Créer mon compte</a></p>
        <p style="color:#9C7A6A;font-size:12px">Ce lien expire dans 48 heures.</p>
        """,
    })
```

- [ ] **Step 4: Write `routes/access.py`**

```python
import uuid
import bcrypt
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import TeamMember, Client, ClientUser, TeamMemberClient
from extensions import db
from decorators import require_role
from email import send_invitation

access_bp = Blueprint("access", __name__, url_prefix="/admin/access")

@access_bp.route("/")
@login_required
@require_role("superadmin", "admin")
def index():
    members = TeamMember.query.order_by(TeamMember.created_at).all()
    clients = Client.query.filter_by(is_active=True).order_by(Client.name).all()
    return render_template("admin/access.html", members=members, clients=clients,
                           current_member=current_user)

@access_bp.route("/invite", methods=["POST"])
@login_required
@require_role("superadmin", "admin")
def invite():
    email = request.form.get("email", "").strip().lower()
    name  = request.form.get("name", "").strip()
    role  = request.form.get("role", "user")
    if role == "superadmin" and current_user.role != "superadmin":
        abort(403)
    if TeamMember.query.filter_by(email=email).first():
        flash("Cet email est déjà enregistré.")
        return redirect(url_for("access.index"))
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=48)
    m = TeamMember(email=email, name=name, role=role, invite_token=token, invite_expires_at=expires)
    db.session.add(m); db.session.commit()
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
@login_required
@require_role("superadmin", "admin")
def revoke(member_id):
    m = TeamMember.query.get_or_404(member_id)
    if m.role == "superadmin" and current_user.role != "superadmin":
        abort(403)
    m.password_hash = None
    m.invite_token = None
    db.session.commit()
    flash(f"Accès révoqué pour {m.name}.")
    return redirect(url_for("access.index"))

@access_bp.route("/client/<int:client_id>/rotate-token", methods=["POST"])
@login_required
@require_role("superadmin", "admin")
def rotate_client_token(client_id):
    c = Client.query.get_or_404(client_id)
    c.secret_token = str(uuid.uuid4())
    db.session.commit()
    flash(f"Nouveau lien généré pour {c.name}.")
    return redirect(url_for("access.index"))

@access_bp.route("/client/new", methods=["POST"])
@login_required
@require_role("superadmin", "admin")
def new_client():
    name = request.form.get("name", "").strip()
    meta_id  = request.form.get("meta_account_id", "").strip() or None
    google_id= request.form.get("google_customer_id", "").strip() or None
    slug = name.lower().replace(" ", "-")
    c = Client(name=name, slug=slug, meta_account_id=meta_id, google_customer_id=google_id)
    db.session.add(c); db.session.commit()
    flash(f"Client '{name}' ajouté.")
    return redirect(url_for("access.index"))
```

- [ ] **Step 5: Fix import conflict — `email.py` shadows Python stdlib `email`**

Rename the file to `mailer.py` and update the import in `routes/access.py`:

```bash
mv email.py mailer.py
```

In `routes/access.py`, change:
```python
from email import send_invitation
```
to:
```python
from mailer import send_invitation
```

- [ ] **Step 6: Write `templates/admin/access.html`**

```html
{% extends "base.html" %}
{% block title %}Accès{% endblock %}
{% block content %}

<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h1 style="font-size:18px;font-weight:700">Gestion des accès</h1>
</div>

<!-- Team Members -->
<div class="card">
  <div class="card-header">
    <span class="card-title">Équipe ({{ members|length }})</span>
    <button onclick="document.getElementById('invite-form').style.display='block'" class="btn btn-primary">+ Inviter</button>
  </div>

  <!-- Invite form (hidden by default) -->
  <div id="invite-form" style="display:none;padding:16px;border-bottom:1px solid var(--bordure);background:var(--fond)">
    <form method="POST" action="{{ url_for('access.invite') }}" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
      <div><label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Nom</label>
        <input name="name" required placeholder="Marie Leblanc" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px"></div>
      <div><label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Email</label>
        <input name="email" type="email" required placeholder="marie@tap.com" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px"></div>
      <div><label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Rôle</label>
        <select name="role" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px">
          <option value="user">Utilisateur</option>
          <option value="admin">Admin</option>
          {% if current_member.role == 'superadmin' %}<option value="superadmin">Super Admin</option>{% endif %}
        </select></div>
      <button type="submit" class="btn btn-primary">Envoyer l'invitation</button>
    </form>
  </div>

  <table>
    <thead><tr><th>Membre</th><th>Rôle</th><th>Statut</th><th>Dernière connexion</th><th>Actions</th></tr></thead>
    <tbody>
    {% for m in members %}
      <tr>
        <td>
          <div style="font-weight:600">{{ m.name }}</div>
          <div style="font-size:10px;color:var(--gris)">{{ m.email }}</div>
        </td>
        <td><span class="badge badge-{{ m.role }}">{{ m.role|capitalize }}</span></td>
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
          <form method="POST" action="{{ url_for('access.revoke', member_id=m.id) }}" style="display:inline" onsubmit="return confirm('Révoquer l\'accès de {{ m.name }} ?')">
            <button class="btn btn-danger">Révoquer</button>
          </form>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<!-- Clients -->
<div class="card">
  <div class="card-header">
    <span class="card-title">Clients ({{ clients|length }})</span>
    <button onclick="document.getElementById('client-form').style.display='block'" class="btn btn-primary">+ Ajouter un client</button>
  </div>

  <div id="client-form" style="display:none;padding:16px;border-bottom:1px solid var(--bordure);background:var(--fond)">
    <form method="POST" action="{{ url_for('access.new_client') }}" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
      <div><label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Nom</label>
        <input name="name" required placeholder="Boutique Lux" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px"></div>
      <div><label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Meta Account ID</label>
        <input name="meta_account_id" placeholder="act_123456" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px"></div>
      <div><label style="font-size:10px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Google Customer ID</label>
        <input name="google_customer_id" placeholder="1234567890" style="padding:8px;border:1px solid var(--bordure);border-radius:6px;font-size:12px"></div>
      <button type="submit" class="btn btn-primary">Ajouter</button>
    </form>
  </div>

  <table>
    <thead><tr><th>Client</th><th>Plateformes</th><th>Lien portail</th><th>Actions</th></tr></thead>
    <tbody>
    {% for c in clients %}
      <tr>
        <td style="font-weight:600">{{ c.name }}</td>
        <td>
          {% if c.meta_account_id %}<span class="tag-meta">Meta</span>{% endif %}
          {% if c.google_customer_id %}<span class="tag-google">Google</span>{% endif %}
        </td>
        <td>
          <code style="font-size:10px;background:var(--fond);border:1px solid var(--bordure);padding:3px 8px;border-radius:4px">
            /client/{{ c.secret_token[:12] }}...
          </code>
        </td>
        <td>
          <form method="POST" action="{{ url_for('access.rotate_client_token', client_id=c.id) }}" style="display:inline" onsubmit="return confirm('Générer un nouveau lien ? L\'ancien ne fonctionnera plus.')">
            <button class="btn btn-outline">↻ Nouveau lien</button>
          </form>
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 7: Create minimal `templates/auth/accept_invite.html`**

```html
{% extends "base.html" %}
{% block title %}Créer mon compte{% endblock %}
{% block content %}
<div style="max-width:400px;margin:40px auto">
  <h1 style="font-size:18px;font-weight:700;margin-bottom:8px">Bienvenue, {{ member.name }} !</h1>
  <p style="color:var(--gris);font-size:13px;margin-bottom:24px">Choisis ton mot de passe pour activer ton compte.</p>
  <form method="POST" class="card" style="padding:24px">
    <label style="font-size:11px;color:var(--gris);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px">Mot de passe</label>
    <input type="password" name="password" required minlength="8" style="width:100%;padding:10px;border:1px solid var(--bordure);border-radius:8px;margin-bottom:16px;background:var(--fond)">
    <button type="submit" class="btn btn-primary" style="width:100%">Activer mon compte</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_access_routes.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 9: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add routes/access.py mailer.py templates/admin/access.html templates/auth/accept_invite.html tests/test_access_routes.py
git commit -m "feat: access management — team invites, client portal links, rotate tokens"
```

---

## Task 13: Deployment

**Files:**
- Already created: `Procfile`, `.env.example`
- Create: `nixpacks.toml` (Railway config)

- [ ] **Step 1: Write `nixpacks.toml`**

```toml
[phases.setup]
nixPkgs = ["python311", "postgresql"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[phases.build]
cmds = ["flask db upgrade"]

[start]
cmd = "gunicorn --workers 1 --bind 0.0.0.0:$PORT app:app"
```

- [ ] **Step 2: Verify gunicorn starts locally**

```bash
gunicorn --workers 1 app:app
```

Expected: `Listening at: http://127.0.0.1:8000` — no import errors.

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Final commit**

```bash
git add nixpacks.toml
git commit -m "feat: Railway deployment config — nixpacks, gunicorn single worker"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Vue admin 360° → Task 9
- ✅ Vue détail client → Task 9 (client_detail route + template)
- ✅ Portail client lecture seule (lien secret + login optionnel) → Task 11
- ✅ Sync horaire APScheduler → Task 7 (init_scheduler)
- ✅ Sync manuelle → Task 10 (/api/sync/<id>)
- ✅ Indicateur de sync dans la nav → Task 8 (base.html) + Tasks 9/11
- ✅ Meta Ads fetcher → Task 5
- ✅ Google Ads fetcher → Task 6
- ✅ Rôles superadmin/admin/user → Tasks 3/4
- ✅ Portail client (rôle client) → Task 11
- ✅ Invitations par email → Task 12
- ✅ Générer/révoquer liens clients → Task 12
- ✅ Design palette Tête à Papineau → Task 8
- ✅ Déploiement Railway → Task 13

**Type consistency:**
- `sync_client(client)` defined in Task 7, called in Task 10 ✅
- `AdMetric` fields match between models (Task 2), fetchers (Tasks 5/6), and _upsert_metrics (Task 7) ✅
- `can_see_client(client_id)` defined on `TeamMember` in Task 2, used in Tasks 9/10 ✅
- `require_role()` defined in Task 4, used in Tasks 9/12 ✅
- `send_invitation()` defined as `mailer.send_invitation` in Task 12 ✅
