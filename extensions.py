from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

login_manager.login_view = "auth.login"
login_manager.login_message = "Connecte-toi pour accéder à cette page."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    from models import TeamMember
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    member = db.session.get(TeamMember, uid)
    if member is not None and member.role not in ('admin', 'client'):
        member.role = 'admin'
        db.session.commit()
    return member
