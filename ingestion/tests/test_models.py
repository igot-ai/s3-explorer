"""Unit tests for core data models."""

import pytest
from ingestion.core.models import (
    FileStatus,
    Catalog,
    FileContext,
    FolderContext,
    IngestionJobConfig,
    ClassificationResult,
    PipelineResult,
)


class TestCatalog:
    """Test Catalog data model."""

    def test_catalog_creation(self):
        """Test creating a valid catalog."""
        catalog = Catalog(
            id="test-catalog",
            information="Test documents",
            content="Description of test catalog",
            fetch_all_metadata=True,
            metadata_scan={"field1": "string", "field2": "boolean"}
        )
        assert catalog.id == "test-catalog"
        assert catalog.information == "Test documents"
        assert catalog.fetch_all_metadata is True
        assert len(catalog.metadata_scan) == 2

    def test_catalog_validation_empty_id(self):
        """Test that empty catalog ID raises ValueError."""
        with pytest.raises(ValueError, match="Catalog id cannot be empty"):
            Catalog(id="", information="Test", content="Test")

    def test_catalog_validation_empty_information(self):
        """Test that empty information raises ValueError."""
        with pytest.raises(ValueError, match="Catalog information cannot be empty"):
            Catalog(id="test", information="", content="Test")


class TestFileContext:
    """Test FileContext data model."""

    def test_file_context_creation(self):
        """Test creating a file context."""
        file_ctx = FileContext(source_path="s3://bucket/file.pdf")
        assert file_ctx.source_path == "s3://bucket/file.pdf"
        assert file_ctx.status == FileStatus.PENDING
        assert file_ctx.is_failed() is False
        assert file_ctx.is_successful() is False

    def test_file_context_successful(self):
        """Test successful file processing."""
        file_ctx = FileContext(
            source_path="s3://bucket/file.pdf",
            status=FileStatus.UPLOADED
        )
        assert file_ctx.is_successful() is True
        assert file_ctx.is_failed() is False

    def test_file_context_failed(self):
        """Test failed file processing."""
        file_ctx = FileContext(
            source_path="s3://bucket/file.pdf",
            status=FileStatus.FAILED,
            error_message="Test error"
        )
        assert file_ctx.is_failed() is True
        assert file_ctx.is_successful() is False


class TestFolderContext:
    """Test FolderContext data model."""

    def test_folder_context_creation(self):
        """Test creating a folder context."""
        folder_ctx = FolderContext(folder_path="s3://bucket/folder1/")
        assert folder_ctx.folder_path == "s3://bucket/folder1/"
        assert len(folder_ctx.files) == 0

    def test_add_file(self):
        """Test adding files to folder context."""
        folder_ctx = FolderContext(folder_path="s3://bucket/folder1/")
        file_ctx = FileContext(source_path="s3://bucket/folder1/file.pdf")
        
        folder_ctx.add_file(file_ctx)
        
        assert len(folder_ctx.files) == 1
        assert file_ctx.parent_folder == "s3://bucket/folder1/"

    def test_get_successful_files(self):
        """Test retrieving successful files."""
        folder_ctx = FolderContext(folder_path="s3://bucket/folder1/")
        
        file1 = FileContext(source_path="file1.pdf", status=FileStatus.UPLOADED)
        file2 = FileContext(source_path="file2.pdf", status=FileStatus.FAILED)
        file3 = FileContext(source_path="file3.pdf", status=FileStatus.UPLOADED)
        
        folder_ctx.add_file(file1)
        folder_ctx.add_file(file2)
        folder_ctx.add_file(file3)
        
        successful = folder_ctx.get_successful_files()
        assert len(successful) == 2

    def test_get_failed_files(self):
        """Test retrieving failed files."""
        folder_ctx = FolderContext(folder_path="s3://bucket/folder1/")
        
        file1 = FileContext(source_path="file1.pdf", status=FileStatus.UPLOADED)
        file2 = FileContext(source_path="file2.pdf", status=FileStatus.FAILED)
        
        folder_ctx.add_file(file1)
        folder_ctx.add_file(file2)
        
        failed = folder_ctx.get_failed_files()
        assert len(failed) == 1
        assert failed[0].source_path == "file2.pdf"

    def test_aggregate_by_catalog(self):
        """Test aggregating files by catalog."""
        folder_ctx = FolderContext(folder_path="s3://bucket/folder1/")
        
        file1 = FileContext(
            source_path="file1.pdf",
            classified_catalog_id="catalog1",
            status=FileStatus.UPLOADED
        )
        file2 = FileContext(
            source_path="file2.pdf",
            classified_catalog_id="catalog1",
            status=FileStatus.UPLOADED
        )
        file3 = FileContext(
            source_path="file3.pdf",
            classified_catalog_id="catalog2",
            status=FileStatus.UPLOADED
        )
        
        folder_ctx.add_file(file1)
        folder_ctx.add_file(file2)
        folder_ctx.add_file(file3)
        
        folder_ctx.aggregate_by_catalog()
        
        assert len(folder_ctx.catalog_summary) == 2
        assert len(folder_ctx.catalog_summary["catalog1"]) == 2
        assert len(folder_ctx.catalog_summary["catalog2"]) == 1


class TestIngestionJobConfig:
    """Test IngestionJobConfig data model."""

    def test_job_config_creation(self):
        """Test creating a job configuration."""
        catalog = Catalog(id="test", information="Test", content="Test")
        config = IngestionJobConfig(
            source_path="s3://bucket/source/",
            catalogs=[catalog],
            pages_to_read=3
        )
        assert config.source_path == "s3://bucket/source/"
        assert len(config.catalogs) == 1
        assert config.pages_to_read == 3
        assert config.recursive is True

    def test_job_config_validation_empty_source(self):
        """Test that empty source_path raises ValueError."""
        catalog = Catalog(id="test", information="Test", content="Test")
        with pytest.raises(ValueError, match="source_path cannot be empty"):
            IngestionJobConfig(source_path="", catalogs=[catalog])

    def test_job_config_validation_no_catalogs(self):
        """Test that no catalogs raises ValueError."""
        with pytest.raises(ValueError, match="At least one catalog must be provided"):
            IngestionJobConfig(source_path="s3://bucket/", catalogs=[])

    def test_job_config_validation_invalid_pages(self):
        """Test that invalid pages_to_read raises ValueError."""
        catalog = Catalog(id="test", information="Test", content="Test")
        with pytest.raises(ValueError, match="pages_to_read must be at least 1"):
            IngestionJobConfig(
                source_path="s3://bucket/",
                catalogs=[catalog],
                pages_to_read=0
            )

    def test_get_catalog_by_id(self):
        """Test finding catalog by ID."""
        catalog1 = Catalog(id="cat1", information="Test1", content="Test1")
        catalog2 = Catalog(id="cat2", information="Test2", content="Test2")
        config = IngestionJobConfig(
            source_path="s3://bucket/",
            catalogs=[catalog1, catalog2]
        )
        
        found = config.get_catalog_by_id("cat2")
        assert found is not None
        assert found.id == "cat2"
        
        not_found = config.get_catalog_by_id("cat3")
        assert not_found is None


class TestClassificationResult:
    """Test ClassificationResult data model."""

    def test_classification_result_creation(self):
        """Test creating a classification result."""
        result = ClassificationResult(
            catalog_id="test-catalog",
            confidence=0.95,
            reasoning="High confidence match",
            metadata={"field1": "value1"}
        )
        assert result.catalog_id == "test-catalog"
        assert result.confidence == 0.95
        assert result.reasoning == "High confidence match"
        assert result.metadata["field1"] == "value1"

    def test_classification_result_validation_confidence(self):
        """Test that invalid confidence raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            ClassificationResult(
                catalog_id="test",
                confidence=1.5,
                reasoning="Test"
            )


class TestPipelineResult:
    """Test PipelineResult data model."""

    def test_pipeline_result_creation(self):
        """Test creating a pipeline result."""
        folder_ctx = FolderContext(folder_path="s3://bucket/folder1/")
        result = PipelineResult(
            total_folders=1,
            total_files=10,
            successful=8,
            failed=2,
            folder_contexts=[folder_ctx],
            execution_time_seconds=45.5
        )
        assert result.total_folders == 1
        assert result.total_files == 10
        assert result.successful == 8
        assert result.failed == 2

    def test_get_success_rate(self):
        """Test calculating success rate."""
        result = PipelineResult(
            total_folders=1,
            total_files=10,
            successful=8,
            failed=2,
            folder_contexts=[]
        )
        assert result.get_success_rate() == 80.0

    def test_get_success_rate_zero_files(self):
        """Test success rate with zero files."""
        result = PipelineResult(
            total_folders=0,
            total_files=0,
            successful=0,
            failed=0,
            folder_contexts=[]
        )
        assert result.get_success_rate() == 0.0

    def test_get_summary(self):
        """Test getting pipeline summary."""
        result = PipelineResult(
            total_folders=2,
            total_files=100,
            successful=95,
            failed=5,
            folder_contexts=[],
            execution_time_seconds=120.5
        )
        summary = result.get_summary()
        assert summary["total_folders"] == 2
        assert summary["total_files"] == 100
        assert summary["successful"] == 95
        assert summary["failed"] == 5
        assert "95.00%" in summary["success_rate"]
        assert "120.50s" in summary["execution_time"]

