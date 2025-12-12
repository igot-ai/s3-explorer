"""Unified LLM classifier supporting multiple providers."""

import json
import logging
import dspy
from typing import List, Optional
from .base import Classifier
from ..core.models import Catalog, ClassificationResult
from ingestion.env import (
    LLM_PROVIDER, 
    LLM_MODEL_ID, 
    LLM_API_KEY, 
    LLM_API_BASE_URL, 
    LLM_API_VERSION, 
    LLM_MAX_TOKEN, 
    LLM_TEMPERATURE
)
from ingestion.utils.llm_helper import LLMHelper

logger = logging.getLogger(__name__)


class FileClassification(dspy.Signature):
    """Phân loại nội dung tệp vào danh mục phù hợp nhất dựa trên nội dung và tên file."""
    
    # Input fields
    categories = dspy.InputField(desc="Danh sách danh mục hợp lệ để chọn từ (JSON format)")
    category_ids = dspy.InputField(desc="Danh sách ID danh mục hợp lệ để chọn từ")
    file_name = dspy.InputField(desc="Tên tệp bao gồm phần mở rộng")
    file_content = dspy.InputField(desc="Nội dung thực tế của tệp để phân loại")
    
    # Output fields
    category_id = dspy.OutputField(desc="ID danh mục phù hợp nhất từ category_ids")
    confidence = dspy.OutputField(desc="Độ tin cậy từ 0.0 đến 5.0 (số thực)", type=float)
    reason = dspy.OutputField(desc="Lý do ngắn gọn cho việc phân loại")

class LLMClassifier(Classifier):
    """Unified LLM classifier with pluggable provider backends.
    
    Supports multiple LLM providers through a single interface:
    - OpenAI (GPT-4, GPT-3.5-turbo)
    - Anthropic (Claude 3)
    - Ollama (Local models)
    - Azure OpenAI
    - Any OpenAI-compatible API
    """

    def __init__(
        self,
        provider: str = LLM_PROVIDER,
        model_id: Optional[str] = LLM_MODEL_ID,
        api_key: Optional[str] = LLM_API_KEY,
        base_url: Optional[str] = LLM_API_BASE_URL,
        api_version: Optional[str] = LLM_API_VERSION,
        **kwargs
    ):
        """Initialize LLM classifier.
        
        Args:
            provider: LLM provider (openai, anthropic, ollama, azure)
            model: Model to use (defaults based on provider)
            api_key: API key (required for openai, anthropic, azure)
            base_url: Custom base URL (for ollama or custom endpoints)
            **kwargs: Additional provider-specific arguments
        """
        self.provider = provider
        self.model = LLMHelper.format_model_id_name(model_id, provider)
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version
        self.kwargs = kwargs

    def classify(
        self,
        file_content: str,
        file_name: str,
        catalogs: List[Catalog]
    ) -> ClassificationResult:
        """Classify document text against available catalogs.
        
        Args:
            file_content: Document text to classify
            file_name: Document name to classify
            catalogs: List of available catalogs
            
        Returns:
            ClassificationResult with best matching catalog ID and confidence
        """
        fallback_classification = ClassificationResult(
            category_id="unknown",
            confidence=0,
            reason=f"{self.provider} not available"
        )
        
        try:
            classifier = dspy.Predict(FileClassification)

            category_ids = [catalog.id for catalog in catalogs]
            categories_str = json.dumps(
                [{"id": catalog.to_dict().get("id"), "information": catalog.to_dict().get("information")} for catalog in catalogs],
                ensure_ascii=False
            )
            
            llm = dspy.LM(
                model=self.model,
                api_key=self.api_key,
                api_base=self.base_url,
                api_version=self.api_version,
                max_tokens=LLM_MAX_TOKEN,
                temperature=LLM_TEMPERATURE,
                cache=False,
                **self.kwargs
            )

            with dspy.context(lm=llm):
                prediction = classifier(
                    categories=categories_str,
                    category_ids=str(category_ids),
                    file_name=file_name,
                    file_content=file_content,
                )

            # Extract separate fields from prediction
            category_id = getattr(prediction, "category_id", None)
            confidence = getattr(prediction, "confidence", None)
            reason = getattr(prediction, "reason", None)
            
            logger.info(f"Classification result: category_id={category_id}, confidence={confidence}, reason={reason}")
            
            if category_id:
                return ClassificationResult(
                    category_id=str(category_id).strip(),
                    confidence=confidence if confidence else 0,
                    reason=str(reason).strip() if reason else ""
                )
            else:
                return fallback_classification

        except Exception as e:
            logger.error(f"DSPy classification failed: {e}")
            return fallback_classification
