"""S3 Explorer Application Entry Point.

Run with: uvicorn main:app --reload --port 5001
Or:       python main.py
"""

import os
import sys
from pathlib import Path

from fastapi import FastAPI

# Ensure src/ is importable when running from repo root without installation.
_PROJECT_ROOT = Path(__file__).resolve().parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from dataroutine.shared.config.s3_config import s3_config
from dataroutine.shared.main import create_app


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


app = FastAPI()
app = create_app(app)

if __name__ == "__main__":
    import uvicorn

    check_aws_credentials()
    # Check if we're in production environment
    is_production = os.environ.get("PRODUCTION", "false").lower() == "true"

    if is_production:
        # Production settings
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 5001)),
            reload=False,
        )
    else:
        # Development settings
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=5001,
            reload=True,
        )
