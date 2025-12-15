"""pdfplumber document reader implementation."""

from shared._logging import get_logger
from pathlib import Path
from ingestion.core.readers.base import DocumentReader

logger = get_logger(__name__)


class PDFPlumberReader(DocumentReader):
    """Read PDF documents using pdfplumber.
    
    pdfplumber is excellent for extracting tables and structured data from PDFs.
    Install with: pip install pdfplumber
    """

    def __init__(self):
        """Initialize pdfplumber reader."""
        try:
            import pdfplumber
            self.pdfplumber = pdfplumber
            self.available = True
        except ImportError:
            logger.warning("pdfplumber not available")
            self.available = False

    def can_read(self, file_path: Path) -> bool:
        """Check if this reader can handle PDF files.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file is PDF and pdfplumber is available
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
            logger.error("pdfplumber not available")
            return ""
        
        try:
            with self.pdfplumber.open(str(file_path)) as pdf:
                text_parts = []
                
                # Read up to max_pages or total pages, whichever is smaller
                pages_to_read = min(max_pages, len(pdf.pages))
                
                for i in range(pages_to_read):
                    page = pdf.pages[i]
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                
                full_text = "\n\n".join(text_parts)
                logger.debug(f"Extracted {len(full_text)} characters from {pages_to_read} pages of {file_path.name}")
                return full_text
                
        except Exception as e:
            logger.error(f"Error reading PDF with pdfplumber: {str(e)}")
            return ""

    def read_full_document(self, file_path: Path) -> str:
        """Extract text from the entire PDF document.
        
        Args:
            file_path: Path to the PDF document
            
        Returns:
            Extracted text
        """
        if not self.available:
            logger.error("pdfplumber not available")
            return ""
        
        try:
            with self.pdfplumber.open(str(file_path)) as pdf:
                text_parts = []
                
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                
                full_text = "\n\n".join(text_parts)
                logger.debug(f"Extracted {len(full_text)} characters from full document {file_path.name}")
                return full_text
                
        except Exception as e:
            logger.error(f"Error reading full PDF with pdfplumber: {str(e)}")
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
            with self.pdfplumber.open(str(file_path)) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logger.error(f"Error getting page count: {str(e)}")
            return 0

    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats.
        
        Returns:
            List of extensions
        """
        return ['.pdf']

    def extract_tables(self, file_path: Path, page_num: int = 0) -> list:
        """Extract tables from a specific page (pdfplumber specialty).
        
        Args:
            file_path: Path to the PDF document
            page_num: Page number (0-indexed)
            
        Returns:
            List of tables (each table is a list of rows)
        """
        if not self.available:
            logger.error("pdfplumber not available")
            return []
        
        try:
            with self.pdfplumber.open(str(file_path)) as pdf:
                if page_num < len(pdf.pages):
                    page = pdf.pages[page_num]
                    tables = page.extract_tables()
                    return tables if tables else []
                return []
        except Exception as e:
            logger.error(f"Error extracting tables: {str(e)}")
            return []

