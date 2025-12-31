"""Abstract base class for document classification."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from dataroutine.modules.ingestion.core.models import Catalog, ClassificationResult


class Classifier(ABC):
    """Abstract interface for document classification using LLM."""

    @abstractmethod
    def classify(
        self, file_content: str, file_name: str, catalogs: List[Catalog]
    ) -> ClassificationResult:
        """Classify document text against available catalogs."""
        pass

    @abstractmethod
    def extract_metadata(self, text: str, catalog: Catalog) -> Dict[str, Any]:
        """Extract metadata fields defined in catalog.metadata_scan.

        Args:
            text: Document text to extract from
            catalog: Catalog defining metadata schema

        Returns:
            Dictionary with field names and extracted values
        """
        pass
