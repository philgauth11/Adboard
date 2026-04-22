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

    import models  # noqa: F401 — ensure models are registered with SQLAlchemy metadata

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
