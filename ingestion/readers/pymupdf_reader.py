"""PyMuPDF (fitz) document reader implementation."""

import logging
from pathlib import Path
from typing import Optional
from .base import DocumentReader

logger = logging.getLogger(__name__)


class PyMuPDFReader(DocumentReader):
    """Read PDF documents using PyMuPDF (fitz).
    
    PyMuPDF is fast and supports images, making it ideal for most PDFs.
    Install with: pip install PyMuPDF
    """

    def __init__(self):
        """Initialize PyMuPDF reader."""
        try:
            import fitz
            self.fitz = fitz
            self.available = True
        except ImportError:
            logger.warning("PyMuPDF (fitz) not available, PDF reading will not work")
            self.available = False

    def can_read(self, file_path: Path) -> bool:
        """Check if this reader can handle PDF files.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file is PDF and PyMuPDF is available
        """
        return self.available and file_path.suffix.lower() == '.pdf'

    def read_pages(self, file_path: Path, max_pages: int = 3) -> str:
        """Extract text from the first N pages of a PDF.
        
        Args:
            file_path: Path to the PDF document
            max_pages: Maximum number of pages to read
            
        Returns:
            Extracted text
        """
        if not self.available:
            logger.error("PyMuPDF not available")
            return ""
        
        try:
            doc = self.fitz.open(str(file_path))
            text_parts = []
            
            # Read up to max_pages or total pages, whichever is smaller
            pages_to_read = min(max_pages, len(doc))
            
            for page_num in range(pages_to_read):
                page = doc[page_num]
                text = page.get_text()
                if text:
                    text_parts.append(text)
            
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            logger.debug(f"Extracted {len(full_text)} characters from {pages_to_read} pages of {file_path.name}")
            return full_text
            
        except Exception as e:
            logger.error(f"Error reading PDF with PyMuPDF: {str(e)}")
            return ""

    def read_full_document(self, file_path: Path) -> str:
        """Extract text from the entire PDF document.
        
        Args:
            file_path: Path to the PDF document
            
        Returns:
            Extracted text
        """
        if not self.available:
            logger.error("PyMuPDF not available")
            return ""
        
        try:
            doc = self.fitz.open(str(file_path))
            text_parts = []
            
            for page in doc:
                text = page.get_text()
                if text:
                    text_parts.append(text)
            
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            logger.debug(f"Extracted {len(full_text)} characters from full document {file_path.name}")
            return full_text
            
        except Exception as e:
            logger.error(f"Error reading full PDF with PyMuPDF: {str(e)}")
            return ""

    def get_page_count(self, file_path: Path) -> int:
        """Get total number of pages in the PDF.
        
        Args:
            file_path: Path to the PDF document
            
        Returns:
            Number of pages
        """
        if not self.available:
            return 0
        
        try:
            doc = self.fitz.open(str(file_path))
            page_count = len(doc)
            doc.close()
            return page_count
        except Exception as e:
            logger.error(f"Error getting page count: {str(e)}")
            return 0

    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats.
        
        Returns:
            List of extensions
        """
        return ['.pdf']

