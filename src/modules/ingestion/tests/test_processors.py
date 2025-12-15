"""Unit tests for file processors."""

import pytest
from pathlib import Path
import tempfile
import zipfile
from ingestion.processors.base import FileProcessor, FileProcessorChain
from ingestion.processors.converter import DocxToPdfConverter
from ingestion.processors.extractor import ArchiveExtractor, SimpleZipExtractor
from ingestion.core.models import FileContext, FileStatus


class TestFileProcessorChain:
    """Test FileProcessorChain."""

    def test_chain_initialization(self):
        """Test chain initialization."""
        processor1 = SimpleZipExtractor()
        processor2 = SimpleZipExtractor()
        
        chain = FileProcessorChain([processor1, processor2])
        
        assert len(chain.get_processors()) == 2

    def test_chain_add_processor(self):
        """Test adding processor to chain."""
        chain = FileProcessorChain([])
        assert len(chain.get_processors()) == 0
        
        processor = SimpleZipExtractor()
        chain.add_processor(processor)
        
        assert len(chain.get_processors()) == 1

    def test_chain_process_with_match(self):
        """Test chain processing with matching processor."""
        processor = SimpleZipExtractor()
        chain = FileProcessorChain([processor])
        
        file_ctx = FileContext(source_path="test.zip", file_type="zip")
        
        # Create a real zip file for testing
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            with zipfile.ZipFile(tmp.name, 'w') as zf:
                zf.writestr("test.txt", "test content")
            file_ctx.local_path = tmp.name
            temp_path = tmp.name
        
        try:
            output_dir = Path(tempfile.mkdtemp())
            results = chain.process(file_ctx, output_dir)
            
            assert isinstance(results, list)
            # Should extract at least one file
            assert len(results) >= 1
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_chain_process_no_match(self):
        """Test chain processing with no matching processor."""
        processor = SimpleZipExtractor()
        chain = FileProcessorChain([processor])
        
        file_ctx = FileContext(source_path="test.pdf", file_type="pdf")
        output_dir = Path(tempfile.mkdtemp())
        
        results = chain.process(file_ctx, output_dir)
        
        # Should return original file
        assert len(results) == 1
        assert results[0].source_path == "test.pdf"


class TestSimpleZipExtractor:
    """Test SimpleZipExtractor."""

    def test_can_process_zip(self):
        """Test can_process identifies ZIP files."""
        extractor = SimpleZipExtractor()
        
        zip_file = FileContext(source_path="test.zip", file_type="zip")
        non_zip_file = FileContext(source_path="test.pdf", file_type="pdf")
        
        assert extractor.can_process(zip_file) is True
        assert extractor.can_process(non_zip_file) is False

    def test_extract_zip_file(self):
        """Test ZIP file extraction."""
        extractor = SimpleZipExtractor()
        
        # Create a test ZIP file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            with zipfile.ZipFile(tmp.name, 'w') as zf:
                zf.writestr("file1.txt", "content1")
                zf.writestr("file2.txt", "content2")
            temp_zip = tmp.name
        
        try:
            file_ctx = FileContext(
                source_path="archive.zip",
                local_path=temp_zip,
                file_type="zip"
            )
            
            output_dir = Path(tempfile.mkdtemp())
            results = extractor.process(file_ctx, output_dir)
            
            assert len(results) == 2
            assert all(r.status == FileStatus.PENDING for r in results)
            assert all("archive.zip" in r.source_path for r in results)
        finally:
            Path(temp_zip).unlink(missing_ok=True)

    def test_extract_invalid_zip(self):
        """Test extraction of invalid ZIP file."""
        extractor = SimpleZipExtractor()
        
        # Create an invalid ZIP file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(b"not a zip file")
            temp_path = tmp.name
        
        try:
            file_ctx = FileContext(
                source_path="bad.zip",
                local_path=temp_path,
                file_type="zip"
            )
            
            output_dir = Path(tempfile.mkdtemp())
            results = extractor.process(file_ctx, output_dir)
            
            assert len(results) == 1
            assert results[0].status == FileStatus.FAILED
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_get_supported_extensions(self):
        """Test getting supported extensions."""
        extractor = SimpleZipExtractor()
        extensions = extractor.get_supported_extensions()
        
        assert ".zip" in extensions


class TestArchiveExtractor:
    """Test ArchiveExtractor (patool-based)."""

    def test_initialization(self):
        """Test extractor initialization."""
        extractor = ArchiveExtractor()
        
        # May or may not be available depending on installation
        assert isinstance(extractor.available, bool)

    def test_supported_formats(self):
        """Test that all patool formats are listed."""
        extractor = ArchiveExtractor()
        extensions = extractor.get_supported_extensions()
        
        # Check some key formats
        assert ".zip" in extensions
        assert ".rar" in extensions
        assert ".7z" in extensions
        assert ".tar" in extensions
        assert ".gz" in extensions

    def test_can_process_common_formats(self):
        """Test can_process for common archive formats."""
        extractor = ArchiveExtractor()
        
        if not extractor.available:
            pytest.skip("patool not available")
        
        zip_file = FileContext(source_path="test.zip", file_type="zip")
        rar_file = FileContext(source_path="test.rar", file_type="rar")
        pdf_file = FileContext(source_path="test.pdf", file_type="pdf")
        
        assert extractor.can_process(zip_file) is True
        assert extractor.can_process(rar_file) is True
        assert extractor.can_process(pdf_file) is False

    def test_compound_extensions(self):
        """Test detection of compound extensions like .tar.gz."""
        extractor = ArchiveExtractor()
        
        if not extractor.available:
            pytest.skip("patool not available")
        
        # Create file with compound extension
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            temp_path = tmp.name
        
        try:
            file_ctx = FileContext(
                source_path="archive.tar.gz",
                local_path=temp_path,
                file_type="gz"
            )
            
            # Should recognize compound extension
            assert extractor.can_process(file_ctx)
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestDocxToPdfConverter:
    """Test DocxToPdfConverter."""

    def test_initialization(self):
        """Test converter initialization."""
        converter = DocxToPdfConverter()
        assert converter.libreoffice_path == "soffice"

    def test_can_process_docx(self):
        """Test can_process identifies DOCX files."""
        converter = DocxToPdfConverter()
        
        docx_file = FileContext(source_path="test.docx", file_type="docx")
        doc_file = FileContext(source_path="test.doc", file_type="doc")
        pdf_file = FileContext(source_path="test.pdf", file_type="pdf")
        
        assert converter.can_process(docx_file) is True
        assert converter.can_process(doc_file) is True
        assert converter.can_process(pdf_file) is False

    def test_get_supported_extensions(self):
        """Test getting supported extensions."""
        converter = DocxToPdfConverter()
        extensions = converter.get_supported_extensions()
        
        assert ".docx" in extensions
        assert ".doc" in extensions

    def test_libreoffice_availability_check(self):
        """Test LibreOffice availability check."""
        converter = DocxToPdfConverter()
        
        # This will return True or False depending on system
        is_available = converter.is_libreoffice_available()
        assert isinstance(is_available, bool)

    def test_process_without_libreoffice(self):
        """Test processing fails gracefully without LibreOffice."""
        converter = DocxToPdfConverter(libreoffice_path="/nonexistent/soffice")
        
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            temp_path = tmp.name
        
        try:
            file_ctx = FileContext(
                source_path="test.docx",
                local_path=temp_path,
                file_type="docx"
            )
            
            output_dir = Path(tempfile.mkdtemp())
            results = converter.process(file_ctx, output_dir)
            
            # Should fail but return file context with error
            assert len(results) == 1
            assert results[0].status == FileStatus.FAILED
        finally:
            Path(temp_path).unlink(missing_ok=True)

