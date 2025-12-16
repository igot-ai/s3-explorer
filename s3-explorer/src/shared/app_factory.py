import os
from pathlib import Path

from flask import Flask, jsonify, make_response, redirect, request
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, generate_csrf
from src.modules.ingestion.routers import ingestion_bp
from src.modules.s3_explore.web.routes import s3_explore_bp
from src.shared._logging import get_logger
from src.shared.config.s3_config import s3_config


def create_app(test_config=None):
    # Setup paths
    # This file is in src/shared/app_factory.py
    # _SRC_DIR is ../..
    # Note: When installed as a package, we need to locate resources relative to the package files
    # or rely on MANIFEST.in/package_data
    # For now, we assume standard file structure or dev environment
    _SHARED_DIR = Path(__file__).resolve().parent
    # We need to find where s3_explore/web is.
    # If installed, 's3_explore' is a sibling package to 'shared'.
    # We can try to import it and find its path.
    import src.modules.s3_explore

    _S3_EXPLORE_ROOT = Path(src.modules.s3_explore.__file__).parent
    _S3_EXPLORE_WEB_DIR = _S3_EXPLORE_ROOT / "web"

    app = Flask(
        __name__,
        template_folder=str(_S3_EXPLORE_WEB_DIR / "templates"),
        static_folder=str(_S3_EXPLORE_WEB_DIR / "static"),
        static_url_path="/static",
    )

    if test_config:
        app.config.update(test_config)

    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024 * 1024  # 1 TB
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
    app.config["WTF_CSRF_TIME_LIMIT"] = None
    app.config["WTF_CSRF_SSL_STRICT"] = False
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["WTF_CSRF_METHODS"] = ["POST", "PUT", "PATCH", "DELETE"]
    app.config["WTF_CSRF_CHECK_DEFAULT"] = False

    logger = get_logger(__name__)

    # Enable CORS
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:3000",
                    "http://localhost:3001",
                    "http://127.0.0.1:3000",
                ],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            }
        },
    )

    csrf = CSRFProtect()
    csrf.init_app(app)

    # Register Blueprints
    app.register_blueprint(s3_explore_bp)
    app.register_blueprint(ingestion_bp)

    csrf.exempt(ingestion_bp)

    @app.before_request
    def _force_https_in_prod():
        if (
            not request.is_secure
            and not app.debug
            and os.environ.get("PRODUCTION", "false").lower() == "true"
        ):
            url = request.url.replace("http://", "https://", 1)
            return redirect(url, code=301)

    @app.after_request
    def _set_csrf_cookie_and_header(response):
        if not request.path.startswith("/static/") and not request.path.startswith(
            "/assets/"
        ):
            csrf_token = generate_csrf()
            response.set_cookie("csrf_token", csrf_token, samesite="Strict")
            response.headers["X-CSRF-Token"] = csrf_token
        return response

    @app.route("/get-csrf-token")
    def get_csrf_token():
        token = generate_csrf()
        response = make_response(jsonify({"csrf_token": token}))
        response.set_cookie("csrf_token", token, samesite="Strict")
        return response

    if not s3_config.aws_access_key_id or not s3_config.aws_secret_access_key:
        logger.warning("AWS credentials not set.")

    return app
