from pathlib import Path
from typing import Any

import pymupdf
from dataroutine.modules.ingestion.core.readers.base import DocumentReader
from dataroutine.modules.ingestion.core.readers.extractor.markitdown_file_extraction import (
    MarkitdownFileExtractor,
)


class MarkitdownReader(DocumentReader):
    """Document reader that uses MarkItDown for text extraction.

    Supports PDF files via MarkitdownFileExtractor.
    """

    def __init__(self, model: Any = None):
        self._extractor = MarkitdownFileExtractor(model=model)

    def can_read(self, file_path: Path) -> bool:
        """Check if this reader can handle the given file type."""
        extension = Path(file_path).suffix.lower()
        return extension in self.get_supported_formats()

    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats.

        Returns:
            List of extensions
        """
        return [".pdf"]

    def get_page_count(self, file_path: Path) -> int:
        """Get total number of pages in the document."""
        doc = pymupdf.open(str(file_path))
        page_count = len(doc)
        doc.close()
        return page_count

    def read_pages(self, file_path: Path, max_pages: int = 3) -> str:
        """Extract text from the first N pages of the document."""
        if not self.can_read(file_path):
            return ""
        return self._extractor.read_pages(str(file_path), max_pages)

    def read_full_document(self, file_path: Path) -> str:
        """Extract text from the entire document."""
        if not self.can_read(file_path):
            return ""
        return self._extractor.extract_content_from_file(str(file_path))
