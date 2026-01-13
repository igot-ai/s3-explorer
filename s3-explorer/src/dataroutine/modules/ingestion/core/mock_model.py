from typing import Any
import dspy
from dataroutine.shared._logging import get_logger

logger = get_logger(__name__)


class MockOpenAIClient:
    """Mock OpenAI client for MarkItDown compatibility."""

    def __init__(self, model: Any, **kwargs):
        # Create the nested structure expected by MarkItDown: client.chat.completions.create()
        self.chat = MockChat(model)


class MockChat:
    """Mock OpenAI chat object for MarkItDown compatibility."""

    def __init__(self, model: Any):
        self.completions = MockCompletions(model)


class MockCompletions:
    """Mock OpenAI completions object for MarkItDown compatibility."""

    def __init__(self, model: Any):
        self.model = model

    def create(self, **kwargs):
        """Mock OpenAI chat completions create method that matches the expected interface."""
        # Check if the model has a completion method
        if hasattr(self.model, "completion"):
            response = self.model.completion(**kwargs)
        else:
            # Fallback to calling the model directly (e.g., dspy.LM)
            messages = kwargs.get("messages", [])
            response = self.model(messages=messages)

        # 1. If it's already an OpenAI-like response object, extract the content
        # This handles classes like TensorLLamaLLM
        if hasattr(response, 'choices') and len(response.choices) > 0:
            content = response.choices[0].message.content
        elif isinstance(response, dict) and 'choices' in response:
            content = response['choices'][0].get('message', {}).get('content', '')
        # 2. If it's a list (common in dspy), join it
        elif isinstance(response, list):
            content = "\n".join(str(item) for item in response)
        # 3. Fallback to string conversion
        else:
            content = str(response)

        return MockResponse(content)


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
