import json
from typing import Any, Dict, List, Optional

import dspy
from dataroutine.modules.ingestion.core.classifiers.base import Classifier
from dataroutine.modules.ingestion.core.models import Catalog, ClassificationResult
from dataroutine.modules.ingestion.env import (
    LLM_API_BASE_URL,
    LLM_API_KEY,
    LLM_API_VERSION,
    LLM_MAX_TOKEN,
    LLM_MODEL_ID,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
)
from dataroutine.modules.ingestion.utils.llm_helper import LLMHelper
from dataroutine.shared._logging import get_logger

logger = get_logger(__name__)


class FileClassification(dspy.Signature):
    """Classify file content into the most appropriate category based on its content and file name."""

    # Input fields
    categories = dspy.InputField(
        desc="List of valid categories to choose from (JSON format)"
    )
    category_ids = dspy.InputField(desc="List of valid category IDs to choose from")
    file_name = dspy.InputField(desc="File name including extension")
    file_content = dspy.InputField(desc="Actual content of the file to be classified")

    # Output fields
    category_id = dspy.OutputField(desc="The most appropriate category ID from category_ids")
    confidence = dspy.OutputField(
        desc="Confidence score from 0.0 to 5.0 (float)", type=float
    )
    reason = dspy.OutputField(desc="Short reason for the classification")


class FileExtractMetadata(dspy.Signature):
    """
    Extract requested metadata fields from the file content.
    The model should focus on inferring and filling in values for metadata fields
    based on the actual content of the file.
    """

    # Input fields
    file_content = dspy.InputField(
        desc="Actual content of the file (parsed text) used to extract metadata"
    )
    metadata = dspy.InputField(
        desc="List or schema describing the metadata fields to be extracted"
    )

    # Output fields
    extracted_metadata = dspy.OutputField(
        desc=(
            "Extracted metadata values corresponding to the requested fields, "
            "returning the exact structure of the input metadata"
        ),
        type=dict,
    )


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
        **kwargs,
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

        self._llm = dspy.LM(
            model=self.model,
            api_key=self.api_key,
            api_base=self.base_url,
            api_version=self.api_version,
            max_tokens=LLM_MAX_TOKEN,
            temperature=LLM_TEMPERATURE,
            cache=False,
            **self.kwargs,
        )

    def classify(
        self, file_content: str, file_name: str, catalogs: List[Catalog]
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
            category_id="unknown", confidence=0, reason=f"{self.provider} not available"
        )

        try:
            classifier = dspy.Predict(FileClassification)

            category_ids = [catalog.id for catalog in catalogs]
            categories_str = json.dumps(
                [
                    {
                        "id": catalog.to_dict().get("id"),
                        "instruction": catalog.to_dict().get("instruction"),
                    }
                    for catalog in catalogs
                ],
                ensure_ascii=False,
            )

            with dspy.context(lm=self._llm):
                prediction = classifier(
                    categories=categories_str,
                    category_ids=str(category_ids),
                    file_name=file_name,
                    file_content=file_content,
                )

            category_id = getattr(prediction, "category_id", None)
            confidence = getattr(prediction, "confidence", None)
            reason = getattr(prediction, "reason", None)

            logger.info(
                f"Classification result: category_id={category_id}, confidence={confidence}, reason={reason}"
            )

            if category_id:
                return ClassificationResult(
                    category_id=str(category_id).strip(),
                    confidence=confidence if confidence else 0,
                    reason=str(reason).strip() if reason else "",
                )
            else:
                return fallback_classification

        except Exception as e:
            logger.error(f"DSPy classification failed: {e}")
            return fallback_classification

    def extract_metadata(self, text: str, catalog: Catalog) -> Dict[str, Any]:
        try:
            extractor = dspy.Predict(FileExtractMetadata)

            with dspy.context(lm=self._llm):
                result = extractor(
                    file_content=text,
                    metadata=catalog.metadata_scan,
                )

            extracted_metadata = getattr(result, "extracted_metadata", {})

            if isinstance(extracted_metadata, str):
                extracted_metadata = LLMHelper.parse_llm_json(extracted_metadata)

            logger.info(
                f"Metadata extraction result: extracted_metadata={extracted_metadata}"
            )

            return extracted_metadata if isinstance(extracted_metadata, dict) else {}

        except Exception as e:
            logger.error(f"DSPy metadata extraction failed: {e}")
            return {}
