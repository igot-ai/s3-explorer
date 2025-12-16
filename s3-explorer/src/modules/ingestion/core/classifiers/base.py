"""Abstract base class for document classification."""

from abc import ABC, abstractmethod
from typing import List

from src.modules.ingestion.core.models import Catalog, ClassificationResult


class Classifier(ABC):
    """Abstract interface for document classification using LLM."""

    @abstractmethod
    def classify(
        self, file_content: str, file_name: str, catalogs: List[Catalog]
    ) -> ClassificationResult:
        """Classify document text against available catalogs."""
        pass
