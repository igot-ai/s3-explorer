import json
import re

from dataroutine.shared._logging import get_logger

logger = get_logger(__name__)


class LLMHelper:
    @staticmethod
    def format_model_id_name(model_id: str, provider: str) -> str:
        """Format the model ID for the given provider."""
        match provider:
            case "claude" | "openai":
                return model_id
            case "gemini" | "azure":
                return f"{provider}/{model_id}"
        return model_id

    @staticmethod
    def parse_llm_json(text: str) -> dict:
        """
        Robustly extract and parse a JSON object from LLM output.
        """
        if not isinstance(text, str):
            return {}

        # 1. Remove markdown code fences
        cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()

        # 2. Try direct parse first (fast path)
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 3. Extract first JSON object using regex
        JSON_OBJECT_RE = re.compile(r"\{(?:[^{}]|(?R))*\}", re.DOTALL)
        match = JSON_OBJECT_RE.search(cleaned)
        if not match:
            logger.warning("No JSON object found in LLM output")
            return {}

        json_str = match.group(0)

        # 4. Fix common JSON issues
        json_str = re.sub(r",\s*}", "}", json_str)  # trailing comma object
        json_str = re.sub(r",\s*]", "]", json_str)  # trailing comma array

        try:
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Failed to parse extracted JSON: {e}")
            return {}
