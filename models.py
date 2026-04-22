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
