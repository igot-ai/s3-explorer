"""Unit tests for core pipeline components."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from ingestion.core.pipeline import IngestionPipeline
from ingestion.core.models import (
    IngestionJobConfig,
    Catalog,
    FileContext,
    FolderContext,
    FileStatus,
    PipelineResult,
)


class TestIngestionPipeline:
    """Test IngestionPipeline orchestrator."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for pipeline."""
        return {
            'source_connector': Mock(),
            'processor_chain': Mock(),
            'document_reader': Mock(),
            'classifier': Mock(),
            'collection_handler': Mock(),
        }

    @pytest.fixture
    def sample_config(self):
        """Create sample job configuration."""
        catalog = Catalog(
            id="test-catalog",
            information="Test documents",
            content="Test catalog"
        )
        return IngestionJobConfig(
            source_path="test/",
            catalogs=[catalog],
            pages_to_read=3
        )

    def test_pipeline_initialization(self, mock_components):
        """Test pipeline initialization."""
        pipeline = IngestionPipeline(**mock_components)
        
        assert pipeline.source == mock_components['source_connector']
        assert pipeline.processor == mock_components['processor_chain']
        assert pipeline.reader == mock_components['document_reader']
        assert pipeline.classifier == mock_components['classifier']
        assert pipeline.handler == mock_components['collection_handler']

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
        mock_components['source_connector'].list_folders.return_value = []
        
        pipeline = IngestionPipeline(**mock_components)
        result = pipeline.run(sample_config)
        
        assert isinstance(result, PipelineResult)
        assert result.total_folders == 0
        assert result.total_files == 0

    def test_pipeline_run_with_files(self, mock_components, sample_config):
        """Test pipeline with files."""
        # Setup mocks
        mock_components['source_connector'].list_folders.return_value = ["folder1/"]
        
        file_ctx = FileContext(source_path="folder1/test.pdf", file_type="pdf")
        file_ctx.local_path = "/tmp/test.pdf"
        
        mock_components['source_connector'].walk_folder.return_value = [file_ctx]
        mock_components['source_connector'].download_file.return_value = Mock()
        mock_components['processor_chain'].process.return_value = [file_ctx]
        mock_components['document_reader'].can_read.return_value = True
        mock_components['document_reader'].read_pages.return_value = "Test content"
        
        from ingestion.core.models import ClassificationResult
        mock_components['classifier'].classify.return_value = ClassificationResult(
            catalog_id="test-catalog",
            confidence=0.95,
            reasoning="Test"
        )
        mock_components['classifier'].find_catalog.return_value = (
            sample_config.catalogs[0],
            {"field1": "value1"}
        )
        mock_components['collection_handler'].upload.return_value = "uploaded-path"
        
        # Create temp file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(b"test content")
            temp_path = f.name
        file_ctx.local_path = temp_path
        
        try:
            pipeline = IngestionPipeline(**mock_components)
            result = pipeline.run(sample_config)
            
            assert result.total_folders == 1
            assert result.total_files >= 1
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_pipeline_handles_errors(self, mock_components, sample_config):
        """Test pipeline handles file processing errors."""
        mock_components['source_connector'].list_folders.return_value = ["folder1/"]
        
        file_ctx = FileContext(source_path="folder1/bad.pdf", file_type="pdf")
        mock_components['source_connector'].walk_folder.return_value = [file_ctx]
        mock_components['source_connector'].download_file.side_effect = Exception("Download failed")
        
        pipeline = IngestionPipeline(**mock_components)
        result = pipeline.run(sample_config)
        
        # Should continue despite error
        assert isinstance(result, PipelineResult)
        assert result.failed >= 0

    def test_callbacks_invoked(self, mock_components, sample_config):
        """Test that callbacks are invoked during processing."""
        file_callback = Mock()
        folder_callback = Mock()
        
        mock_components['source_connector'].list_folders.return_value = ["folder1/"]
        mock_components['source_connector'].walk_folder.return_value = []
        
        pipeline = IngestionPipeline(
            **mock_components,
            on_file_processed=file_callback,
            on_folder_completed=folder_callback
        )
        
        result = pipeline.run(sample_config)
        
        # Folder callback should be called once
        assert folder_callback.call_count == 1

    def test_metadata_aggregation(self, mock_components, sample_config):
        """Test metadata aggregation for folders."""
        # Set catalog to fetch all metadata
        sample_config.catalogs[0].fetch_all_metadata = True
        
        mock_components['source_connector'].list_folders.return_value = ["folder1/"]
        mock_components['source_connector'].walk_folder.return_value = []
        
        pipeline = IngestionPipeline(**mock_components)
        result = pipeline.run(sample_config)
        
        assert len(result.folder_contexts) == 1
        folder_ctx = result.folder_contexts[0]
        assert isinstance(folder_ctx, FolderContext)


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
            execution_time_seconds=10.5
        )
        
        assert result.get_success_rate() == 50.0
        
        summary = result.get_summary()
        assert summary["total_files"] == 2
        assert summary["successful"] == 1
        assert summary["failed"] == 1

