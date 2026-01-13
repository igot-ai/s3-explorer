import pytest
from unittest.mock import MagicMock, patch
from typing import Any
from markitdown import MarkItDown

from dataroutine.modules.ingestion.core.mock_model import MockOpenAIClient, MockResponse
from dataroutine.modules.ingestion.core.readers.extractor.markitdown_file_extraction import MarkitdownFileExtractor
from dataroutine.modules.ingestion.core.readers.markitdown_reader import MarkitdownReader

class MockTensorLLM:
    """Mock that behaves like TensorLLamaLLM."""
    def __init__(self, model_name="test-model"):
        self.model = model_name
        
    def completion(self, **kwargs):
        # Return an OpenAI-like response object
        mock_resp = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "extracted text from tensorllm"
        mock_resp.choices = [mock_choice]
        return mock_resp

class MockCallableModel:
    """Mock that behaves like dspy.LM (callable)."""
    def __call__(self, messages=None, **kwargs):
        return ["text from dspy"]

class TestMockOpenAIClient:
    def test_with_completion_method(self):
        tensor_llm = MockTensorLLM()
        client = MockOpenAIClient(model=tensor_llm)
        
        # Test the structure
        assert hasattr(client, "chat")
        assert hasattr(client.chat, "completions")
        
        # Test creation
        response = client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
        assert isinstance(response, MockResponse)
        assert response.choices[0].message.content == "extracted text from tensorllm"

    def test_with_callable_model(self):
        dspy_model = MockCallableModel()
        client = MockOpenAIClient(model=dspy_model)
        
        response = client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
        assert response.choices[0].message.content == "text from dspy"

    def test_content_extraction_variants(self):
        # Test dict response
        dict_model = MagicMock()
        dict_model.completion.return_value = {"choices": [{"message": {"content": "dict content"}}]}
        client = MockOpenAIClient(model=dict_model)
        assert client.chat.completions.create().choices[0].message.content == "dict content"
        
        # Test list response (fallback)
        list_model = MagicMock(side_effect=lambda **k: ["item1", "item2"])
        del list_model.completion # Ensure it uses __call__
        client = MockOpenAIClient(model=list_model)
        assert client.chat.completions.create().choices[0].message.content == "item1\nitem2"

class TestMarkitdownFileExtractor:
    @patch('dataroutine.modules.ingestion.core.readers.extractor.markitdown_file_extraction.dspy.LM')
    @patch('dataroutine.modules.ingestion.core.readers.extractor.markitdown_file_extraction.LLMHelper')
    def test_initialization_with_model(self, mock_helper, mock_dspy):
        mock_helper.format_model_id_name.return_value = "formatted-name"
        custom_model = MockTensorLLM(model_name="custom-name")
        
        extractor = MarkitdownFileExtractor(model=custom_model)
        md, prompt = extractor._choose_markitdown_model()
        
        # Should not have called dspy.LM
        mock_dspy.assert_not_called()
        assert md._llm_model == "custom-name"
        assert isinstance(md._llm_client, MockOpenAIClient)
        assert md._llm_client.chat.completions.model == custom_model

    @patch('dataroutine.modules.ingestion.core.readers.extractor.markitdown_file_extraction.dspy.LM')
    @patch('dataroutine.modules.ingestion.core.readers.extractor.markitdown_file_extraction.LLMHelper')
    def test_initialization_without_model_falls_back_to_dspy(self, mock_helper, mock_dspy):
        mock_helper.format_model_id_name.return_value = "formatted-name"
        mock_dspy_instance = MagicMock()
        mock_dspy.return_value = mock_dspy_instance
        
        extractor = MarkitdownFileExtractor()
        md, prompt = extractor._choose_markitdown_model()
        
        mock_dspy.assert_called_once()
        assert md._llm_model == "formatted-name"
        assert md._llm_client.chat.completions.model == mock_dspy_instance

class TestMarkitdownReader:
    def test_reader_passes_model_to_extractor(self):
        custom_model = MockTensorLLM()
        reader = MarkitdownReader(model=custom_model)
        assert reader._extractor.model == custom_model
