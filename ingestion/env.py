import os
from pathlib import Path

from dotenv import load_dotenv


# Load the env vars
def _load_env(var_name: str) -> str:
    try:
        var_value = _load_optional_env(var_name, "")
        return var_value
    except KeyError as key_error:
        raise EnvironmentError(f"Env var {var_name} does not exist. Error: {key_error}")


def _load_optional_env(var_name: str, default_value: str) -> str:
    return os.environ.get(var_name, default_value)

# Load the .env file
DOT_ENV_FILE_PATH = Path(__file__).parent / ".env"
print(f"Loading .env file from: {DOT_ENV_FILE_PATH}")
load_dotenv(DOT_ENV_FILE_PATH, override=True)

# LLM
LLM_PROVIDER = _load_env("LLM_PROVIDER")
LLM_MODEL_ID = _load_env("LLM_MODEL_ID")
LLM_API_KEY = _load_env("LLM_API_KEY")
LLM_API_BASE_URL = _load_env("LLM_API_BASE_URL")
LLM_API_VERSION = _load_env("LLM_API_VERSION")

# Config
