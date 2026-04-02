from flask import Flask
from app.config import Config
from app.models import db
import json
import os

# Pre-import model modules to avoid local variable shadowing in create_app
import app.models.dimensions  # noqa
import app.models.staging  # noqa
import app.models.allocation  # noqa
import app.models.workflow  # noqa


def create_app(config_class=Config):
    flask_app = Flask(__name__)
    flask_app.config.from_object(config_class)

    # Ensure instance and upload dirs exist
    os.makedirs(os.path.join(flask_app.config["BASE_DIR"], "instance"), exist_ok=True)
    os.makedirs(flask_app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(flask_app)

    # Register blueprints
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.upload import bp as upload_bp
    from app.routes.rules import bp as rules_bp
    from app.routes.batch import bp as batch_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.testdata import bp as testdata_bp

    flask_app.register_blueprint(dashboard_bp)
    flask_app.register_blueprint(upload_bp, url_prefix="/upload")
    flask_app.register_blueprint(rules_bp, url_prefix="/rules")
    flask_app.register_blueprint(batch_bp, url_prefix="/batch")
    flask_app.register_blueprint(reports_bp, url_prefix="/reports")
    flask_app.register_blueprint(testdata_bp, url_prefix="/testdata")

    with flask_app.app_context():
        db.create_all()

    # Custom Jinja filter for parsing JSON in templates
    flask_app.jinja_env.filters["from_json"] = lambda s: json.loads(s) if s else {}

    return flask_app
