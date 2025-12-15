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
