"""Unit tests for core pipeline components."""

import io
from unittest.mock import Mock

import pytest
from ingestion.core.models import (
    Catalog,
    ClassificationResult,
    FileContext,
    FileStatus,
    FolderContext,
    IngestionJobConfig,
    PipelineResult,
)
from ingestion.core.pipeline import IngestionPipeline


class TestIngestionPipeline:
    """Test IngestionPipeline orchestrator."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for pipeline."""
        return {
            "source_connector": Mock(),
            "processor_chain": Mock(),
            "document_reader": Mock(),
            "classifier": Mock(),
            "collection_handler": Mock(),
        }

    @pytest.fixture
    def sample_config(self):
        """Create sample job configuration."""
        catalog = Catalog(
            id="test-catalog", information="Test documents", content="Test catalog"
        )
        return IngestionJobConfig(
            source_path="test/", catalogs=[catalog], pages_to_read=3
        )

    def test_pipeline_initialization(self, mock_components):
        """Test pipeline initialization."""
        pipeline = IngestionPipeline(**mock_components)

        assert pipeline.source == mock_components["source_connector"]
        assert pipeline.processor == mock_components["processor_chain"]
        assert pipeline.reader == mock_components["document_reader"]
        assert pipeline.classifier == mock_components["classifier"]
        assert pipeline.handler == mock_components["collection_handler"]

    def test_pipeline_with_callbacks(self, mock_components):
        """Test pipeline with callbacks."""
        file_callback = Mock()
        folder_callback = Mock()

        pipeline = IngestionPipeline(
            **mock_components,
            on_file_processed=file_callback,
            on_folder_completed=folder_callback
        )

        assert pipeline.on_file_processed == file_callback
        assert pipeline.on_folder_completed == folder_callback

    def test_pipeline_run_empty_folders(self, mock_components, sample_config):
        """Test pipeline with no folders."""
        mock_components["source_connector"].list_folders.return_value = []

        pipeline = IngestionPipeline(**mock_components)
        result = pipeline.run(sample_config)

        assert isinstance(result, PipelineResult)
        assert result.total_folders == 0
        assert result.total_files == 0
        assert result.successful == 0
        assert result.failed == 0

    def test_pipeline_run_with_files(self, mock_components, sample_config):
        """Test pipeline end-to-end happy path for a single file."""
        mock_components["source_connector"].list_folders.return_value = ["folder1/"]

        file_ctx = FileContext(source_path="folder1/test.pdf", file_type="pdf")
        mock_components["source_connector"].walk_folder.return_value = [file_ctx]
        mock_components["source_connector"].download_file.return_value = io.BytesIO(
            b"pdf bytes"
        )

        # Processor returns same context (already "pdf")
        mock_components["processor_chain"].process.side_effect = lambda fc, _td: [fc]

        mock_components["document_reader"].can_read.return_value = True
        mock_components["document_reader"].read_pages.return_value = "Test content"

        mock_components["classifier"].classify.return_value = ClassificationResult(
            category_id="test-catalog", confidence=4, reason="Test"
        )

        # Legacy handler upload format: asset_id string
        mock_components["collection_handler"].upload.return_value = "asset-123"

        pipeline = IngestionPipeline(**mock_components)
        result = pipeline.run(sample_config)

        assert result.total_folders == 1
        assert result.total_files == 1
        assert result.successful == 1
        assert result.failed == 0

    def test_pipeline_handles_errors(self, mock_components, sample_config):
        """Test pipeline handles file processing errors."""
        mock_components["source_connector"].list_folders.return_value = ["folder1/"]

        file_ctx = FileContext(source_path="folder1/bad.pdf", file_type="pdf")
        mock_components["source_connector"].walk_folder.return_value = [file_ctx]
        mock_components["source_connector"].download_file.side_effect = Exception(
            "Download failed"
        )

        pipeline = IngestionPipeline(**mock_components)
        result = pipeline.run(sample_config)

        # Should continue despite error
        assert isinstance(result, PipelineResult)
        assert result.total_files == 1
        assert result.failed == 1

    def test_callbacks_invoked(self, mock_components, sample_config):
        """Test that callbacks are invoked during processing."""
        file_callback = Mock()
        folder_callback = Mock()

        mock_components["source_connector"].list_folders.return_value = ["folder1/"]
        file_ctx = FileContext(source_path="folder1/test.pdf", file_type="pdf")
        mock_components["source_connector"].walk_folder.return_value = [file_ctx]
        mock_components["source_connector"].download_file.return_value = io.BytesIO(
            b"pdf bytes"
        )
        mock_components["processor_chain"].process.side_effect = lambda fc, _td: [fc]
        mock_components["document_reader"].can_read.return_value = True
        mock_components["document_reader"].read_pages.return_value = "Test content"
        mock_components["classifier"].classify.return_value = ClassificationResult(
            category_id="test-catalog", confidence=3, reason="ok"
        )
        mock_components["collection_handler"].upload.return_value = "asset-123"

        pipeline = IngestionPipeline(
            **mock_components,
            on_file_processed=file_callback,
            on_folder_completed=folder_callback
        )

        result = pipeline.run(sample_config)

        # Folder callback should be called once
        assert folder_callback.call_count == 1
        # File callback should be called once
        assert file_callback.call_count == 1
        assert result.successful == 1

    def test_metadata_aggregation(self, mock_components, sample_config):
        """Test metadata aggregation for folders."""
        # Set catalog to fetch all metadata
        sample_config.catalogs[0].fetch_all_metadata = True

        mock_components["source_connector"].list_folders.return_value = ["folder1/"]
        mock_components["source_connector"].walk_folder.return_value = []

        pipeline = IngestionPipeline(**mock_components)
        result = pipeline.run(sample_config)

        assert len(result.folder_contexts) == 1
        folder_ctx = result.folder_contexts[0]
        assert isinstance(folder_ctx, FolderContext)

    def test_extract_data_upload_dict_updates_metadata(
        self, mock_components, sample_config, tmp_path
    ):
        """Test handler dict upload result updates asset_id and file metadata."""
        pipeline = IngestionPipeline(**mock_components)

        # Create a local file for upload
        local_path = tmp_path / "test.pdf"
        local_path.write_bytes(b"pdf bytes")

        pf = FileContext(
            source_path="folder1/test.pdf",
            local_path=str(local_path),
            file_type="pdf",
            status=FileStatus.CLASSIFIED,
            classified_catalog_id="test-catalog",
            metadata={"existing": "x"},
        )
        folder_ctx = FolderContext(folder_path="folder1/")

        mock_components["collection_handler"].upload.return_value = {
            "asset_id": "asset-1",
            "extracted_metadata": {"field1": "value1"},
        }

        pipeline._extract_data(pf, sample_config, folder_ctx)

        assert pf.status == FileStatus.UPLOADED
        assert getattr(pf, "asset_id") == "asset-1"
        assert pf.metadata["existing"] == "x"
        assert pf.metadata["field1"] == "value1"


class TestPipelineResult:
    """Test PipelineResult helper methods."""

    def test_build_result(self):
        """Test building pipeline result."""
        folder_ctx = FolderContext(folder_path="folder1/")

        file1 = FileContext(source_path="file1.pdf", status=FileStatus.UPLOADED)
        file2 = FileContext(source_path="file2.pdf", status=FileStatus.FAILED)
        folder_ctx.add_file(file1)
        folder_ctx.add_file(file2)

        result = PipelineResult(
            total_folders=1,
            total_files=2,
            successful=1,
            failed=1,
            folder_contexts=[folder_ctx],
            execution_time_seconds=10.5,
        )

        assert result.get_success_rate() == 50.0

        summary = result.get_summary()
        assert summary["total_files"] == 2
        assert summary["successful"] == 1
        assert summary["failed"] == 1
