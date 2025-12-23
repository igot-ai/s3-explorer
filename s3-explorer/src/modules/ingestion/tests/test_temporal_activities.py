"""Unit tests for Temporal activities.

These tests verify that activities can be called and handle errors correctly.
Note: Full integration tests would require Temporal server, but we can test
the activity logic in isolation.
"""

from unittest.mock import Mock, patch

from src.modules.ingestion.temporal.activities import (
    _build_job_config,
    _build_result,
    _create_pipeline,
    run_ingestion_pipeline_activity,
)
from src.modules.ingestion.temporal.models import IngestionJobParams, IngestionResult


class TestActivityHelpers:
    """Test helper functions used by activities."""

    @patch("src.modules.ingestion.temporal.activities.get_storage_provider")
    @patch("src.modules.ingestion.temporal.activities.S3SourceConnector")
    @patch("src.modules.ingestion.temporal.activities.DocxToPdfConverter")
    @patch("src.modules.ingestion.temporal.activities.ArchiveExtractor")
    @patch("src.modules.ingestion.temporal.activities.SimpleZipExtractor")
    @patch("src.modules.ingestion.temporal.activities.FileProcessorChain")
    @patch("src.modules.ingestion.temporal.activities.PyMuPDFReader")
    @patch("src.modules.ingestion.temporal.activities.LLMClassifier")
    @patch("src.modules.ingestion.temporal.activities.DataCollectionAPIHandler")
    @patch("src.modules.ingestion.temporal.activities.IngestionPipeline")
    def test_create_pipeline(
        self,
        mock_pipeline,
        mock_handler,
        mock_classifier,
        mock_reader,
        mock_chain,
        mock_zip,
        mock_archive,
        mock_converter,
        mock_connector,
        mock_provider,
    ):
        """Test pipeline creation helper."""
        params = IngestionJobParams(
            source_path="test/",
            workspace_id="ws",
            project_id="proj",
            auth_token="token",
            catalogs=[{"id": "cat1", "instruction": "Test"}],
            api_base_url="http://api.example.com",
            storage_provider="aws",
            storage_credentials={
                "access_key": "key",
                "secret_key": "secret",
                "bucket": "bucket",
            },
        )

        mock_converter_instance = Mock()
        mock_converter_instance.is_libreoffice_available.return_value = False
        mock_converter.return_value = mock_converter_instance

        mock_archive_instance = Mock()
        mock_archive_instance.available = False
        mock_archive.return_value = mock_archive_instance

        pipeline = _create_pipeline(params)
        assert pipeline is not None
        mock_provider.assert_called_once()
        mock_connector.assert_called_once()

    def test_build_job_config(self):
        """Test job config building."""
        params = IngestionJobParams(
            source_path="test/",
            workspace_id="ws",
            project_id="proj",
            auth_token="token",
            catalogs=[
                {"id": "cat1", "instruction": "Test", "fetch_all_metadata": False}
            ],
            recursive=True,
            pages_to_read=5,
        )

        config = _build_job_config(params)
        assert config.source_path == "test"
        assert config.recursive is True
        assert config.pages_to_read == 5
        assert len(config.catalogs) == 1
        assert config.catalogs[0].id == "cat1"

    def test_build_result(self):
        """Test result building from pipeline result."""
        from src.modules.ingestion.core.models import (
            FileContext,
            FileStatus,
            FolderContext,
            PipelineResult,
        )

        folder_ctx = FolderContext(folder_path="test/")
        file1 = FileContext(source_path="file1.pdf", status=FileStatus.UPLOADED)
        file2 = FileContext(source_path="file2.pdf", status=FileStatus.FAILED)
        folder_ctx.add_file(file1)
        folder_ctx.add_file(file2)

        pipeline_result = PipelineResult(
            total_folders=1,
            total_files=2,
            successful=1,
            failed=1,
            folder_contexts=[folder_ctx],
            execution_time_seconds=10.5,
        )

        result = _build_result(pipeline_result, "task-123")
        assert result.task_id == "task-123"
        assert result.total_folders == 1
        assert result.total_files == 2
        assert result.successful == 1
        assert result.failed == 1
        assert len(result.folders) == 1


class TestRunIngestionPipelineActivity:
    """Test the main ingestion pipeline activity."""

    @patch("src.modules.ingestion.temporal.activities._create_pipeline")
    @patch("src.modules.ingestion.temporal.activities._build_job_config")
    @patch("src.modules.ingestion.temporal.activities._build_result")
    def test_run_ingestion_pipeline_activity_success(
        self, mock_build_result, mock_build_config, mock_create_pipeline
    ):
        """Test successful pipeline execution."""
        params = IngestionJobParams(
            source_path="test/",
            workspace_id="ws",
            project_id="proj",
            auth_token="token",
            catalogs=[{"id": "cat1", "instruction": "Test"}],
            task_id="task-123",
            api_base_url="http://api.example.com",
        )

        mock_pipeline = Mock()
        mock_pipeline.run.return_value = Mock(
            total_folders=1,
            total_files=2,
            successful=2,
            failed=0,
            folder_contexts=[],
            execution_time_seconds=10.0,
            get_success_rate=lambda: 100.0,
        )
        mock_create_pipeline.return_value = mock_pipeline

        mock_result = IngestionResult(
            success=True,
            task_id="task-123",
            total_files=2,
            successful=2,
            failed=0,
        )
        mock_build_result.return_value = mock_result

        result_dict = run_ingestion_pipeline_activity(params)

        assert result_dict["success"] is True
        assert result_dict["task_id"] == "task-123"
        mock_pipeline.run.assert_called_once()

    @patch("src.modules.ingestion.temporal.activities._create_pipeline")
    def test_run_ingestion_pipeline_activity_failure(self, mock_create_pipeline):
        """Test pipeline execution failure."""
        params = IngestionJobParams(
            source_path="test/",
            workspace_id="ws",
            project_id="proj",
            auth_token="token",
            catalogs=[{"id": "cat1", "instruction": "Test"}],
            task_id="task-123",
        )

        mock_create_pipeline.side_effect = ValueError("Invalid configuration")

        result_dict = run_ingestion_pipeline_activity(params)

        assert result_dict["success"] is False
        assert result_dict["task_id"] == "task-123"
        assert "error" in result_dict

    def test_run_ingestion_pipeline_activity_auto_task_id(self):
        """Test that task_id is auto-generated if not provided."""
        params = IngestionJobParams(
            source_path="test/",
            workspace_id="ws",
            project_id="proj",
            auth_token="token",
            catalogs=[{"id": "cat1", "instruction": "Test"}],
            task_id="",  # Empty task_id
        )

        with patch(
            "src.modules.ingestion.temporal.activities._create_pipeline"
        ) as mock_create:
            with patch("src.modules.ingestion.temporal.activities._build_job_config"):
                with patch(
                    "src.modules.ingestion.temporal.activities._build_result"
                ) as mock_result:
                    mock_pipeline = Mock()
                    mock_pipeline.run.return_value = Mock(
                        total_folders=0,
                        total_files=0,
                        successful=0,
                        failed=0,
                        folder_contexts=[],
                        execution_time_seconds=0.0,
                        get_success_rate=lambda: 0.0,
                    )
                    mock_create.return_value = mock_pipeline
                    mock_result.return_value = IngestionResult(
                        success=True,
                        task_id="generated-id",
                        total_files=0,
                        successful=0,
                        failed=0,
                    )

                    result_dict = run_ingestion_pipeline_activity(params)

                    # Task ID should be generated (UUID format)
                    assert "task_id" in result_dict
                    assert len(result_dict["task_id"]) > 0
