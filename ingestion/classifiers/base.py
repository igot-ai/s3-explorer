"""Abstract base class for document classification."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from ..core.models import Catalog, ClassificationResult


class Classifier(ABC):
    """Abstract interface for document classification using LLM.
    
    Implementations should provide methods to:
    - Classify documents against catalogs
    - Extract metadata based on catalog schema
    - Find the best matching catalog
    """

    @abstractmethod
    def classify(
        self,
        text: str,
        catalogs: List[Catalog]
    ) -> ClassificationResult:
        """Classify document text against available catalogs.
        
        Args:
            text: Document text to classify
            catalogs: List of available catalogs
            
        Returns:
            ClassificationResult with best matching catalog ID and confidence
        """
        pass

    @abstractmethod
    def extract_metadata(
        self,
        text: str,
        catalog: Catalog
    ) -> Dict[str, Any]:
        """Extract metadata fields defined in catalog.metadata_scan.
        
        Args:
            text: Document text to extract from
            catalog: Catalog defining metadata schema
            
        Returns:
            Dictionary with field names and extracted values
        """
        pass

    def find_catalog(
        self,
        catalog_id: str,
        extracted_text: str,
        catalogs: List[Catalog]
    ) -> Tuple[Optional[Catalog], Dict[str, Any]]:
        """Find catalog by ID and extract its metadata.
        
        This is a convenience method that combines catalog lookup and metadata extraction.
        
        Args:
            catalog_id: ID of the catalog to find
            extracted_text: Document text
            catalogs: List of available catalogs
            
        Returns:
            Tuple of (Catalog, metadata_dict) or (None, {}) if not found
        """
        # Find the catalog
        catalog = next((c for c in catalogs if c.id == catalog_id), None)
        if catalog is None:
            return None, {}
        
        # Extract metadata for this catalog
        metadata = self.extract_metadata(extracted_text, catalog)
        return catalog, metadata

    def build_classification_prompt(self, text: str, catalogs: List[Catalog]) -> str:
        """Build the prompt for classification (template method).
        
        Can be overridden by subclasses for custom prompting.
        
        Args:
            text: Document text
            catalogs: Available catalogs
            
        Returns:
            Formatted prompt string
        """
        catalog_descriptions = "\n".join([
            f"- ID: {c.id}\n  Criteria: {c.information}\n  Description: {c.content}"
            for c in catalogs
        ])
        
        return f"""Analyze the following document text and classify it into one of the categories.

CATEGORIES:
{catalog_descriptions}

DOCUMENT TEXT:
{text[:4000]}

Respond with JSON: {{"catalog_id": "...", "confidence": 0.0-1.0, "reasoning": "..."}}"""

    def build_metadata_prompt(self, text: str, catalog: Catalog) -> str:
        """Build the prompt for metadata extraction (template method).
        
        Can be overridden by subclasses for custom prompting.
        
        Args:
            text: Document text
            catalog: Catalog with metadata schema
            
        Returns:
            Formatted prompt string
        """
        metadata_fields = "\n".join([
            f"- {field}: {description}"
            for field, description in catalog.metadata_scan.items()
        ])
        
        return f"""Extract the following metadata from this document:

METADATA FIELDS TO EXTRACT:
{metadata_fields}

DOCUMENT TEXT:
{text[:4000]}

Respond with JSON containing the extracted metadata fields."""


class MetadataExtractor(ABC):
    """Abstract interface for metadata extraction.
    
    Separate from Classifier to follow Single Responsibility Principle.
    Can be combined with a Classifier or used independently.
    """

    @abstractmethod
    def extract(
        self,
        text: str,
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract metadata based on a schema.
        
        Args:
            text: Document text
            schema: Schema defining what to extract
            
        Returns:
            Extracted metadata
        """
        pass

    @abstractmethod
    def validate_metadata(
        self,
        metadata: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> bool:
        """Validate extracted metadata against schema.
        
        Args:
            metadata: Extracted metadata
            schema: Expected schema
            
        Returns:
            True if valid, False otherwise
        """
        pass

