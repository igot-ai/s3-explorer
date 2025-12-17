"""Unit tests for Temporal workflow models."""

import pytest
from dataroutine.modules.ingestion.temporal.models import (
    CatalogParams,
    IngestionJobParams,
    IngestionResult,
    StorageCredentials,
)


class TestCatalogParams:
    """Test CatalogParams data model."""

    def test_catalog_params_creation(self):
        """Test creating catalog params."""
        params = CatalogParams(
            id="test-catalog",
            instruction="Test documents",
            fetch_all_metadata=True,
        )
        assert params.id == "test-catalog"
        assert params.instruction == "Test documents"
        assert params.fetch_all_metadata is True

    def test_catalog_params_to_dict(self):
        """Test converting to dictionary."""
        params = CatalogParams(id="cat1", instruction="Test", fetch_all_metadata=False)
        result = params.to_dict()
        assert result == {
            "id": "cat1",
            "instruction": "Test",
            "fetch_all_metadata": False,
        }

    def test_catalog_params_from_dict(self):
        """Test creating from dictionary."""
        data = {"id": "cat1", "instruction": "Test", "fetch_all_metadata": True}
        params = CatalogParams.from_dict(data)
        assert params.id == "cat1"
        assert params.instruction == "Test"
        assert params.fetch_all_metadata is True


class TestStorageCredentials:
    """Test StorageCredentials data model."""

    def test_storage_credentials_creation(self):
        """Test creating storage credentials."""
        creds = StorageCredentials(
            access_key="key",
            secret_key="secret",
            bucket="bucket",
            region="us-east-1",
        )
        assert creds.access_key == "key"
        assert creds.secret_key == "secret"
        assert creds.bucket == "bucket"
        assert creds.region == "us-east-1"

    def test_storage_credentials_to_dict(self):
        """Test converting to dictionary, excluding None values."""
        creds = StorageCredentials(
            access_key="key",
            secret_key="secret",
            bucket="bucket",
            region=None,
        )
        result = creds.to_dict()
        assert "access_key" in result
        assert "secret_key" in result
        assert "bucket" in result
        assert "region" not in result  # None values excluded

    def test_storage_credentials_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "access_key": "key",
            "secret_key": "secret",
            "bucket": "bucket",
            "region": "us-east-1",
        }
        creds = StorageCredentials.from_dict(data)
        assert creds.access_key == "key"
        assert creds.bucket == "bucket"
        assert creds.region == "us-east-1"


class TestIngestionJobParams:
    """Test IngestionJobParams data model."""

    def test_ingestion_job_params_creation(self):
        """Test creating ingestion job params."""
        catalogs = [{"id": "cat1", "instruction": "Test", "fetch_all_metadata": False}]
        params = IngestionJobParams(
            source_path="raw-documents/",
            workspace_id="ws-123",
            project_id="proj-456",
            auth_token="token-789",
            catalogs=catalogs,
        )
        assert params.source_path == "raw-documents/"
        assert params.workspace_id == "ws-123"
        assert params.project_id == "proj-456"
        assert params.auth_token == "token-789"
        assert len(params.catalogs) == 1

    def test_ingestion_job_params_defaults(self):
        """Test default values."""
        catalogs = [{"id": "cat1", "instruction": "Test"}]
        params = IngestionJobParams(
            source_path="path/",
            workspace_id="ws",
            project_id="proj",
            auth_token="token",
            catalogs=catalogs,
        )
        assert params.storage_provider == "aws"
        assert params.recursive is True
        assert params.pages_to_read == 3
        assert params.reader_type == "pymupdf"

    def test_get_catalogs(self):
        """Test converting catalogs to CatalogParams objects."""
        catalogs = [
            {"id": "cat1", "instruction": "Test1", "fetch_all_metadata": False},
            {"id": "cat2", "instruction": "Test2", "fetch_all_metadata": True},
        ]
        params = IngestionJobParams(
            source_path="path/",
            workspace_id="ws",
            project_id="proj",
            auth_token="token",
            catalogs=catalogs,
        )
        catalog_objs = params.get_catalogs()
        assert len(catalog_objs) == 2
        assert catalog_objs[0].id == "cat1"
        assert catalog_objs[1].fetch_all_metadata is True

    def test_to_dict(self):
        """Test converting to dictionary."""
        catalogs = [{"id": "cat1", "instruction": "Test"}]
        params = IngestionJobParams(
            source_path="path/",
            workspace_id="ws",
            project_id="proj",
            auth_token="token",
            catalogs=catalogs,
            task_id="task-123",
        )
        result = params.to_dict()
        assert result["source_path"] == "path/"
        assert result["task_id"] == "task-123"
        assert len(result["catalogs"]) == 1

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "source_path": "path/",
            "workspace_id": "ws",
            "project_id": "proj",
            "auth_token": "token",
            "catalogs": [{"id": "cat1", "instruction": "Test"}],
            "task_id": "task-123",
        }
        params = IngestionJobParams.from_dict(data)
        assert params.source_path == "path/"
        assert params.task_id == "task-123"


class TestIngestionResult:
    """Test IngestionResult data model."""

    def test_ingestion_result_creation(self):
        """Test creating ingestion result."""
        result = IngestionResult(
            success=True,
            task_id="task-123",
            total_folders=2,
            total_files=10,
            successful=8,
            failed=2,
        )
        assert result.success is True
        assert result.task_id == "task-123"
        assert result.total_files == 10

    def test_ingestion_result_failure(self):
        """Test creating failure result."""
        result = IngestionResult.failure("task-123", "Test error")
        assert result.success is False
        assert result.task_id == "task-123"
        assert result.error == "Test error"

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = IngestionResult(
            success=True,
            task_id="task-123",
            total_files=10,
            successful=8,
            failed=2,
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["task_id"] == "task-123"
        assert data["total_files"] == 10

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "success": True,
            "task_id": "task-123",
            "total_folders": 2,
            "total_files": 10,
            "successful": 8,
            "failed": 2,
            "success_rate": "80.00%",
            "execution_time": "45.5s",
        }
        result = IngestionResult.from_dict(data)
        assert result.success is True
        assert result.total_files == 10
        assert result.success_rate == "80.00%"

