from pathlib import Path
from typing import Any

import pymupdf
from dataroutine.modules.ingestion.core.readers.base import DocumentReader
from dataroutine.modules.ingestion.core.readers.extractor.markitdown_file_extraction import (
    MarkitdownFileExtractor,
)
from dataroutine.modules.ingestion.utils.constant import SUPPORTED_DOCUMENT_EXTENSIONS


class MarkitdownReader(DocumentReader):
    """Document reader that uses MarkItDown for text extraction.

    Supports various file formats including PDF, images, and audio via MarkitdownFileExtractor.
    """

    def __init__(self, model: Any = None):
        self._extractor = MarkitdownFileExtractor(model=model)

    def can_read(self, file_path: Path) -> bool:
        """Check if this reader can handle the given file type."""
        return True # Always return True as markitdown will handle validation

    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats.

        Returns:
            List of extensions
        """
        return list(SUPPORTED_DOCUMENT_EXTENSIONS)

    def get_page_count(self, file_path: Path) -> int:
        """Get total number of pages in the document."""
        extension = Path(file_path).suffix.lower()
        if extension == ".pdf":
            try:
                doc = pymupdf.open(str(file_path))
                page_count = len(doc)
                doc.close()
                return page_count
            except Exception:
                return 0
        return 1 # Return 1 for non-PDF files

    def read_pages(self, file_path: Path, max_pages: int = 3) -> str:
        """Extract text from the first N pages of the document."""
        extension = Path(file_path).suffix.lower()
        if extension != ".pdf":
            return self.read_full_document(file_path)
        return self._extractor.read_pages(str(file_path), max_pages)

    def read_full_document(self, file_path: Path) -> str:
        """Extract text from the entire document."""
        if not self.can_read(file_path):
            return ""
        return self._extractor.extract_content_from_file(str(file_path))
