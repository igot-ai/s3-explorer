import dspy

from shared._logging import get_logger

logger = get_logger(__name__)


class MockOpenAIClient:
    """Mock OpenAI client for MarkItDown compatibility."""

    def __init__(self, dspy_model: dspy.LM, api_base: str = None):
        self.dspy_model = dspy_model
        self.api_base = api_base
        self.base_url = api_base

        # Create the nested structure expected by MarkItDown: client.chat.completions.create()
        self.chat = MockChat(dspy_model)


class MockChat:
    """Mock OpenAI chat object for MarkItDown compatibility."""

    def __init__(self, dspy_model: dspy.LM):
        self.dspy_model = dspy_model
        self.completions = MockCompletions(dspy_model)


class MockCompletions:
    """Mock OpenAI completions object for MarkItDown compatibility."""

    def __init__(self, dspy_model: dspy.LM):
        self.dspy_model = dspy_model

    def create(self, **kwargs):
        """Mock OpenAI chat completions create method that matches the expected interface."""
        messages = kwargs.get("messages", [])
        response = self.dspy_model(messages=messages)

        if isinstance(response, list):
            response = "\n".join(str(item) for item in response)
        elif not isinstance(response, str):
            response = str(response)

        return MockResponse(response)


class MockResponse:
    """Mock OpenAI response object that matches the expected structure."""

    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


class MockChoice:
    """Mock OpenAI choice object."""

    def __init__(self, content: str):
        self.message = MockMessage(content)


class MockMessage:
    """Mock OpenAI message object."""

    def __init__(self, content: str):
        self.content = content
