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
def _find_env_file() -> Path:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        env_file = parent / ".env"
        if env_file.exists():
            return env_file

    return Path(__file__).parent.parent.parent.parent / ".env"


DOT_ENV_FILE_PATH = _find_env_file()
load_dotenv(DOT_ENV_FILE_PATH, override=False)

# LLM
LLM_PROVIDER = _load_env("LLM_PROVIDER")
LLM_MODEL_ID = _load_env("LLM_MODEL_ID")
LLM_API_KEY = _load_env("LLM_API_KEY")
LLM_API_BASE_URL = _load_env("LLM_API_BASE_URL")
LLM_API_VERSION = _load_env("LLM_API_VERSION")
LLM_MAX_TOKEN = int(_load_optional_env("LLM_MAX_TOKEN", "36000"))
LLM_TEMPERATURE = float(_load_optional_env("LLM_TEMPERATURE", "0.3"))

# Config
READER_TYPE = _load_optional_env("READER_TYPE", "markitdown")
TEMP_DIR = _load_optional_env("TEMP_DIR", "tmp")
API_BASE_URL = _load_optional_env("API_BASE_URL", "http://localhost:8000/v1/catalog")