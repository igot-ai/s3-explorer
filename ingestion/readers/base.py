"""Abstract base class for document readers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class DocumentReader(ABC):
    """Abstract interface for extracting text from documents.
    
    Implementations should support reading various document formats (PDF, DOCX, etc.).
    """

    @abstractmethod
    def can_read(self, file_path: Path) -> bool:
        """Check if this reader can handle the given file type.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if this reader can handle the file
        """
        pass

    @abstractmethod
    def read_pages(self, file_path: Path, max_pages: int = 3) -> str:
        """Extract text from the first N pages of the document.
        
        Args:
            file_path: Path to the document
            max_pages: Maximum number of pages to read
            
        Returns:
            Extracted text
        """
        pass

    @abstractmethod
    def read_full_document(self, file_path: Path) -> str:
        """Extract text from the entire document.
        
        Args:
            file_path: Path to the document
            
        Returns:
            Extracted text
        """
        pass

    @abstractmethod
    def get_page_count(self, file_path: Path) -> int:
        """Get total number of pages in the document.
        
        Args:
            file_path: Path to the document
            
        Returns:
            Number of pages
        """
        pass

    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats.
        
        Returns:
            List of extensions (e.g., ['.pdf', '.docx'])
        """
        pass

