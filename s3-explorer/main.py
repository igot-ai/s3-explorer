import os
import sys
from pathlib import Path

# Ensure refactored src/ and src/modules/ are importable when running from repo root.
_PROJECT_ROOT = Path(__file__).resolve().parent
_SRC_DIR = _PROJECT_ROOT / "src"
_MODULES_DIR = _SRC_DIR / "modules"
for _p in (str(_SRC_DIR), str(_MODULES_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flask import Flask, jsonify, make_response, redirect, request
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_cors import CORS

from src.modules.ingestion.routers import ingestion_bp
from src.modules.s3_explore.web.routes import s3_explore_bp
from src.shared._logging import get_logger
from src.shared.config.s3_config import s3_config

_WEB_DIR = _PROJECT_ROOT / "src" / "modules" / "s3_explore" / "web"

app = Flask(
    __name__,
    template_folder=str(_WEB_DIR / "templates"),
    static_folder=str(_WEB_DIR / "static"),
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024 * 1024  # 1 TB
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32))
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["WTF_CSRF_SSL_STRICT"] = False
app.config["WTF_CSRF_ENABLED"] = True
app.config["WTF_CSRF_METHODS"] = ["POST", "PUT", "PATCH", "DELETE"]
app.config["WTF_CSRF_CHECK_DEFAULT"] = False  # manual verification in /configure

logger = get_logger(__name__)

# Enable CORS for frontend
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

csrf = CSRFProtect()
csrf.init_app(app)

app.register_blueprint(s3_explore_bp)
app.register_blueprint(ingestion_bp)
csrf.exempt(ingestion_bp)


@app.before_request
def _force_https_in_prod():
    if not request.is_secure and not app.debug:
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)


@app.after_request
def _set_csrf_cookie_and_header(response):
    if not request.path.startswith("/static/"):
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


def check_aws_credentials():
    if (
        not s3_config.aws_access_key_id
        or not s3_config.aws_secret_access_key
        or not s3_config.s3_bucket
    ):
        print(
            "Warning: AWS credentials not set. Please configure them through the web interface."
        )
    else:
        print("AWS credentials are set.")


if __name__ == "__main__":
    check_aws_credentials()
    # Check if we're in production environment
    is_production = os.environ.get("PRODUCTION", "false").lower() == "true"

    if is_production:
        # Production settings
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
    else:
        # Development settings
        app.run(host="0.0.0.0", port=5001, debug=True)
