from flask import Flask
from flask_login import LoginManager
from app.config import Config
from app.models import db
import json
import os

# Pre-import model modules to avoid local variable shadowing in create_app
import app.models.dimensions  # noqa
import app.models.staging  # noqa
import app.models.allocation  # noqa
import app.models.workflow  # noqa
import app.models.auth  # noqa

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app(config_class=Config):
    flask_app = Flask(__name__)
    flask_app.config.from_object(config_class)

    # Ensure instance and upload dirs exist
    os.makedirs(os.path.join(flask_app.config["BASE_DIR"], "instance"), exist_ok=True)
    os.makedirs(flask_app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(flask_app)
    login_manager.init_app(flask_app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.auth import User
        return User.query.get(int(user_id))

    # Register blueprints
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.upload import bp as upload_bp
    from app.routes.rules import bp as rules_bp
    from app.routes.batch import bp as batch_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.testdata import bp as testdata_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.admin import bp as admin_bp

    flask_app.register_blueprint(dashboard_bp)
    flask_app.register_blueprint(upload_bp, url_prefix="/upload")
    flask_app.register_blueprint(rules_bp, url_prefix="/rules")
    flask_app.register_blueprint(batch_bp, url_prefix="/batch")
    flask_app.register_blueprint(reports_bp, url_prefix="/reports")
    flask_app.register_blueprint(testdata_bp, url_prefix="/testdata")
    flask_app.register_blueprint(auth_bp, url_prefix="/auth")
    flask_app.register_blueprint(admin_bp, url_prefix="/admin")

    with flask_app.app_context():
        db.create_all()
        _seed_defaults()

    # Custom Jinja filter for parsing JSON in templates
    flask_app.jinja_env.filters["from_json"] = lambda s: json.loads(s) if s else {}

    return flask_app


def _seed_defaults():
    """Create default groups and admin user if they don't exist."""
    from app.models.auth import User, Group

    if Group.query.first() is not None:
        return

    makers = Group(name="Makers", description="Can create and submit uploads", can_make=True, can_check=False)
    checkers = Group(name="Checkers", description="Can approve/reject uploads", can_make=False, can_check=True)
    admins = Group(name="Admins", description="Full access including user management", can_make=True, can_check=True, is_admin=True)

    db.session.add_all([makers, checkers, admins])
    db.session.flush()

    admin = User(username="admin", display_name="Administrator")
    admin.set_password("admin")
    admin.groups.append(admins)

    maker = User(username="maker1", display_name="Maker User 1")
    maker.set_password("maker1")
    maker.groups.append(makers)

    checker = User(username="checker1", display_name="Checker User 1")
    checker.set_password("checker1")
    checker.groups.append(checkers)

    db.session.add_all([admin, maker, checker])
    db.session.commit()
