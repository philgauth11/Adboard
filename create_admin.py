import os
import sys
import bcrypt
from app import create_app
from extensions import db
from models import TeamMember

password = os.environ.get("ADMIN_PASSWORD")
if not password:
    print("Erreur : définis la variable ADMIN_PASSWORD avant de lancer ce script.")
    sys.exit(1)

app = create_app()
with app.app_context():
    existing = TeamMember.query.filter_by(email="info@teteapapineau.com").first()
    if existing:
        print("Compte info@teteapapineau.com existe déjà.")
        sys.exit(0)
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    m = TeamMember(email="info@teteapapineau.com", name="Philippe", role="superadmin", password_hash=pw_hash)
    db.session.add(m)
    db.session.commit()
    print("Compte superadmin créé : info@teteapapineau.com")
