"""Unit tests for abstract interface classes."""

import pytest
from pathlib import Path
from io import BytesIO
from typing import Iterator, BinaryIO, List, Dict, Any
from ingestion.connectors.base import SourceConnector
from ingestion.processors.base import FileProcessor, FileProcessorChain
from ingestion.readers.base import DocumentReader
from ingestion.classifiers.base import Classifier, MetadataExtractor
from ingestion.handlers.base import CollectionHandler, APICollectionHandler
from ingestion.core.models import (
    FileContext,
    FolderContext,
    Catalog,
    ClassificationResult,
    FileStatus,
)


# Mock implementations for testing


class MockSourceConnector(SourceConnector):
    """Mock implementation of SourceConnector for testing."""

    def list_folders(self, prefix: str = "") -> List[str]:
        return [f"{prefix}folder1/", f"{prefix}folder2/"]

    def walk_folder(self, folder_path: str, recursive: bool = True) -> Iterator[FileContext]:
        yield FileContext(source_path=f"{folder_path}file1.pdf")
        yield FileContext(source_path=f"{folder_path}file2.docx")

    def download_file(self, file_path: str) -> BinaryIO:
        return BytesIO(b"mock file content")

    def get_file_metadata(self, file_path: str) -> dict:
        return {"size": 1024, "last_modified": "2024-01-01"}

    def file_exists(self, file_path: str) -> bool:
        return True


class MockFileProcessor(FileProcessor):
    """Mock implementation of FileProcessor for testing."""

    def can_process(self, file_context: FileContext) -> bool:
        return file_context.source_path.endswith(".docx")

    def process(self, file_context: FileContext, output_dir: Path) -> List[FileContext]:
        converted = FileContext(
            source_path=file_context.source_path,
            local_path=str(output_dir / "converted.pdf"),
            file_type="pdf",
            status=FileStatus.CONVERTED
        )
        return [converted]

    def get_supported_extensions(self) -> List[str]:
        return [".docx", ".doc"]


class MockDocumentReader(DocumentReader):
    """Mock implementation of DocumentReader for testing."""

    def can_read(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def read_pages(self, file_path: Path, max_pages: int = 3) -> str:
        return "Mock extracted text from pages"

    def read_full_document(self, file_path: Path) -> str:
        return "Mock full document text"

    def get_page_count(self, file_path: Path) -> int:
        return 10

    def get_supported_formats(self) -> list[str]:
        return [".pdf"]


class MockClassifier(Classifier):
    """Mock implementation of Classifier for testing."""

    def classify(self, text: str, catalogs: List[Catalog]) -> ClassificationResult:
        return ClassificationResult(
            catalog_id=catalogs[0].id if catalogs else "unknown",
            confidence=0.95,
            reasoning="Mock classification",
            metadata={"field1": "value1"}
        )

    def extract_metadata(self, text: str, catalog: Catalog) -> Dict[str, Any]:
        return {"field1": "extracted_value1", "field2": "extracted_value2"}


class MockMetadataExtractor(MetadataExtractor):
    """Mock implementation of MetadataExtractor for testing."""

    def extract(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        return {key: f"extracted_{key}" for key in schema.keys()}

    def validate_metadata(self, metadata: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        return all(key in metadata for key in schema.keys())


class MockCollectionHandler(CollectionHandler):
    """Mock implementation of CollectionHandler for testing."""

    def upload(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        metadata: Dict[str, Any]
    ) -> str:
        return f"s3://bucket/{catalog.id}/{file_context.source_path}"

    def upload_with_folder_context(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        file_metadata: Dict[str, Any],
        folder_context: FolderContext
    ) -> str:
        return f"s3://bucket/{catalog.id}/{file_context.source_path}"

    def build_destination_path(self, file_context: FileContext, catalog: Catalog) -> str:
        return f"{catalog.target_path}{file_context.source_path}"


class MockAPICollectionHandler(APICollectionHandler):
    """Mock implementation of APICollectionHandler for testing."""

    def __init__(self):
        self._authenticated = False

    def authenticate(self) -> None:
        self._authenticated = True

    def get_collection(self, catalog_id: str) -> Dict:
        return {"id": catalog_id, "name": f"Collection {catalog_id}"}

    def create_collection(self, catalog: Catalog) -> Dict:
        return {"id": catalog.id, "name": catalog.content}

    def update_collection_metadata(self, catalog_id: str, metadata: Dict[str, Any]) -> bool:
        return True

    def is_authenticated(self) -> bool:
        return self._authenticated

    def upload(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        metadata: Dict[str, Any]
    ) -> str:
        return f"api://collection/{catalog.id}/file/{file_context.source_path}"

    def upload_with_folder_context(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        file_metadata: Dict[str, Any],
        folder_context: FolderContext
    ) -> str:
        return f"api://collection/{catalog.id}/file/{file_context.source_path}"

    def build_destination_path(self, file_context: FileContext, catalog: Catalog) -> str:
        return f"api://{catalog.id}/{file_context.source_path}"


# Tests


class TestSourceConnector:
    """Test SourceConnector interface."""

    def test_list_folders(self):
        connector = MockSourceConnector()
        folders = connector.list_folders("test/")
        assert len(folders) == 2
        assert "test/folder1/" in folders

    def test_walk_folder(self):
        connector = MockSourceConnector()
        files = list(connector.walk_folder("folder1/"))
        assert len(files) == 2
        assert isinstance(files[0], FileContext)

    def test_download_file(self):
        connector = MockSourceConnector()
        file_obj = connector.download_file("test.pdf")
        # Check if it's a file-like object
        assert hasattr(file_obj, 'read')
        content = file_obj.read()
        assert content == b"mock file content"

    def test_get_file_metadata(self):
        connector = MockSourceConnector()
        metadata = connector.get_file_metadata("test.pdf")
        assert "size" in metadata
        assert metadata["size"] == 1024

    def test_file_exists(self):
        connector = MockSourceConnector()
        assert connector.file_exists("test.pdf") is True


class TestFileProcessor:
    """Test FileProcessor interface."""

    def test_can_process(self):
        processor = MockFileProcessor()
        docx_file = FileContext(source_path="test.docx")
        pdf_file = FileContext(source_path="test.pdf")
        
        assert processor.can_process(docx_file) is True
        assert processor.can_process(pdf_file) is False

    def test_process(self):
        processor = MockFileProcessor()
        file_ctx = FileContext(source_path="test.docx")
        output_dir = Path("/tmp")
        
        results = processor.process(file_ctx, output_dir)
        assert len(results) == 1
        assert results[0].status == FileStatus.CONVERTED

    def test_get_supported_extensions(self):
        processor = MockFileProcessor()
        extensions = processor.get_supported_extensions()
        assert ".docx" in extensions
        assert ".doc" in extensions


class TestFileProcessorChain:
    """Test FileProcessorChain."""

    def test_process_with_matching_processor(self):
        processor = MockFileProcessor()
        chain = FileProcessorChain([processor])
        
        file_ctx = FileContext(source_path="test.docx")
        results = chain.process(file_ctx, Path("/tmp"))
        
        assert len(results) == 1
        assert results[0].status == FileStatus.CONVERTED

    def test_process_with_no_matching_processor(self):
        processor = MockFileProcessor()
        chain = FileProcessorChain([processor])
        
        file_ctx = FileContext(source_path="test.pdf")
        results = chain.process(file_ctx, Path("/tmp"))
        
        # Should return original file
        assert len(results) == 1
        assert results[0].source_path == "test.pdf"

    def test_add_processor(self):
        chain = FileProcessorChain([])
        assert len(chain.get_processors()) == 0
        
        processor = MockFileProcessor()
        chain.add_processor(processor)
        assert len(chain.get_processors()) == 1


class TestDocumentReader:
    """Test DocumentReader interface."""

    def test_can_read(self):
        reader = MockDocumentReader()
        pdf_path = Path("test.pdf")
        docx_path = Path("test.docx")
        
        assert reader.can_read(pdf_path) is True
        assert reader.can_read(docx_path) is False

    def test_read_pages(self):
        reader = MockDocumentReader()
        text = reader.read_pages(Path("test.pdf"), max_pages=3)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_read_full_document(self):
        reader = MockDocumentReader()
        text = reader.read_full_document(Path("test.pdf"))
        assert isinstance(text, str)
        assert len(text) > 0

    def test_get_page_count(self):
        reader = MockDocumentReader()
        count = reader.get_page_count(Path("test.pdf"))
        assert count == 10

    def test_get_supported_formats(self):
        reader = MockDocumentReader()
        formats = reader.get_supported_formats()
        assert ".pdf" in formats


class TestClassifier:
    """Test Classifier interface."""

    def test_classify(self):
        classifier = MockClassifier()
        catalog = Catalog(id="test", information="Test", content="Test catalog")
        result = classifier.classify("document text", [catalog])
        
        assert isinstance(result, ClassificationResult)
        assert result.catalog_id == "test"
        assert 0.0 <= result.confidence <= 1.0

    def test_extract_metadata(self):
        classifier = MockClassifier()
        catalog = Catalog(
            id="test",
            information="Test",
            content="Test",
            metadata_scan={"field1": "string", "field2": "boolean"}
        )
        metadata = classifier.extract_metadata("document text", catalog)
        
        assert isinstance(metadata, dict)
        assert "field1" in metadata

    def test_find_catalog(self):
        classifier = MockClassifier()
        catalog1 = Catalog(id="cat1", information="Test1", content="Test1")
        catalog2 = Catalog(id="cat2", information="Test2", content="Test2")
        
        found_catalog, metadata = classifier.find_catalog("cat2", "text", [catalog1, catalog2])
        
        assert found_catalog is not None
        assert found_catalog.id == "cat2"
        assert isinstance(metadata, dict)

    def test_find_catalog_not_found(self):
        classifier = MockClassifier()
        catalog = Catalog(id="cat1", information="Test1", content="Test1")
        
        found_catalog, metadata = classifier.find_catalog("cat99", "text", [catalog])
        
        assert found_catalog is None
        assert metadata == {}

    def test_build_classification_prompt(self):
        classifier = MockClassifier()
        catalog = Catalog(id="test", information="Test docs", content="Test")
        prompt = classifier.build_classification_prompt("doc text", [catalog])
        
        assert "test" in prompt.lower()
        assert "doc text" in prompt

    def test_build_metadata_prompt(self):
        classifier = MockClassifier()
        catalog = Catalog(
            id="test",
            information="Test",
            content="Test",
            metadata_scan={"field1": "string"}
        )
        prompt = classifier.build_metadata_prompt("doc text", catalog)
        
        assert "field1" in prompt
        assert "doc text" in prompt


class TestMetadataExtractor:
    """Test MetadataExtractor interface."""

    def test_extract(self):
        extractor = MockMetadataExtractor()
        schema = {"field1": "string", "field2": "boolean"}
        metadata = extractor.extract("document text", schema)
        
        assert isinstance(metadata, dict)
        assert all(key in metadata for key in schema.keys())

    def test_validate_metadata(self):
        extractor = MockMetadataExtractor()
        schema = {"field1": "string", "field2": "boolean"}
        valid_metadata = {"field1": "value", "field2": True}
        invalid_metadata = {"field1": "value"}
        
        assert extractor.validate_metadata(valid_metadata, schema) is True
        assert extractor.validate_metadata(invalid_metadata, schema) is False


class TestCollectionHandler:
    """Test CollectionHandler interface."""

    def test_upload(self):
        handler = MockCollectionHandler()
        file_ctx = FileContext(source_path="test.pdf")
        catalog = Catalog(id="test", information="Test", content="Test")
        file_stream = BytesIO(b"content")
        metadata = {"field1": "value1"}
        
        result = handler.upload(file_ctx, catalog, file_stream, metadata)
        assert isinstance(result, str)
        assert "test.pdf" in result

    def test_upload_with_folder_context(self):
        handler = MockCollectionHandler()
        file_ctx = FileContext(source_path="test.pdf")
        catalog = Catalog(id="test", information="Test", content="Test")
        folder_ctx = FolderContext(folder_path="folder1/")
        file_stream = BytesIO(b"content")
        
        result = handler.upload_with_folder_context(
            file_ctx, catalog, file_stream, {}, folder_ctx
        )
        assert isinstance(result, str)

    def test_build_destination_path(self):
        handler = MockCollectionHandler()
        file_ctx = FileContext(source_path="test.pdf")
        catalog = Catalog(
            id="test",
            information="Test",
            content="Test"
        )
        catalog.target_path = "collections/test/"
        
        path = handler.build_destination_path(file_ctx, catalog)
        assert "collections/test/" in path
        assert "test.pdf" in path

    def test_prepare_metadata(self):
        handler = MockCollectionHandler()
        file_metadata = {"file_field": "value"}
        
        prepared = handler.prepare_metadata(file_metadata)
        assert "file_field" in prepared
        assert prepared["file_field"] == "value"


class TestAPICollectionHandler:
    """Test APICollectionHandler interface."""

    def test_authenticate(self):
        handler = MockAPICollectionHandler()
        assert handler.is_authenticated() is False
        
        handler.authenticate()
        assert handler.is_authenticated() is True

    def test_get_collection(self):
        handler = MockAPICollectionHandler()
        collection = handler.get_collection("test_id")
        
        assert isinstance(collection, dict)
        assert collection["id"] == "test_id"

    def test_create_collection(self):
        handler = MockAPICollectionHandler()
        catalog = Catalog(id="test", information="Test", content="Test Catalog")
        
        collection = handler.create_collection(catalog)
        assert isinstance(collection, dict)
        assert collection["id"] == "test"

    def test_update_collection_metadata(self):
        handler = MockAPICollectionHandler()
        metadata = {"field1": "value1"}
        
        result = handler.update_collection_metadata("test_id", metadata)
        assert result is True

