from app import create_app
from extensions import db
from models import TeamMember
import bcrypt

app = create_app()
with app.app_context():
    pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
    m = TeamMember(email='info@teteapapineau.com', name='Philippe', role='superadmin', password_hash=pw)
    db.session.add(m)
    db.session.commit()
    print('Compte créé !')
