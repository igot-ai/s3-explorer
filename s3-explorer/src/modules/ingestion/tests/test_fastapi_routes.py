"""Unit tests for FastAPI ingestion routes."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.modules.ingestion.routers.ingestion_fastapi import router
from src.modules.ingestion.wrapper import IngestionTaskResult


# Create test app
app = FastAPI()
app.include_router(router)


class TestRunIngestionEndpoint:
    """Test POST /api/v1/ingestion/run endpoint."""
    
    @patch("src.modules.ingestion.routers.ingestion_fastapi.get_ingestion_wrapper")
    @patch("src.modules.ingestion.routers.ingestion_fastapi.AUTH_TOKEN", "test-token")
    def test_run_ingestion_success(self, mock_get_wrapper):
        """Test successful ingestion trigger."""
        mock_wrapper = Mock()
        mock_wrapper.trigger_ingestion.return_value = IngestionTaskResult(
            task_id="task-123",
            status="started",
            success=True,
            error=None,
        )
        mock_get_wrapper.return_value = mock_wrapper
        
        client = TestClient(app)
        response = client.post(
            "/api/v1/ingestion/run",
            json={
                "config": {
                    "source_path": "test/",
                    "workspace_id": "ws-123",
                    "project_id": "proj-456",
                    "auth_token": "token-789",
                },
                "catalogs": [
                    {"id": "cat1", "instruction": "Test", "fetch_all_metadata": False}
                ],
            },
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == "task-123"
        assert data["status"] == "started"
    
    @patch("src.modules.ingestion.routers.ingestion_fastapi.AUTH_TOKEN", "test-token")
    def test_run_ingestion_missing_auth(self, _):
        """Test ingestion trigger without authentication."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/ingestion/run",
            json={
                "config": {
                    "source_path": "test/",
                    "workspace_id": "ws-123",
                    "project_id": "proj-456",
                    "auth_token": "token-789",
                },
                "catalogs": [{"id": "cat1", "instruction": "Test"}],
            },
        )
        
        assert response.status_code == 401
    
    @patch("src.modules.ingestion.routers.ingestion_fastapi.get_ingestion_wrapper")
    @patch("src.modules.ingestion.routers.ingestion_fastapi.AUTH_TOKEN", "test-token")
    def test_run_ingestion_missing_required_fields(self, mock_get_wrapper):
        """Test ingestion trigger with missing required fields."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/ingestion/run",
            json={
                "config": {
                    "source_path": "test/",
                    # Missing workspace_id, project_id, auth_token
                },
                "catalogs": [{"id": "cat1", "instruction": "Test"}],
            },
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Missing required API handler settings" in data["detail"]["message"]


class TestHealthCheckEndpoint:
    """Test GET /api/v1/ingestion/health endpoint."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        client = TestClient(app)
        response = client.get("/api/v1/ingestion/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ingestion-pipeline"


class TestListPrefixesEndpoint:
    """Test POST /api/v1/ingestion/list-prefixes endpoint."""
    
    @patch("src.modules.ingestion.routers.ingestion_fastapi.S3SourceConnector")
    @patch("src.modules.ingestion.routers.ingestion_fastapi.get_storage_provider")
    @patch("src.modules.ingestion.routers.ingestion_fastapi.AUTH_TOKEN", "test-token")
    def test_list_prefixes_success(self, mock_get_provider, mock_connector_class):
        """Test successful prefix listing."""
        mock_provider = Mock()
        mock_get_provider.return_value = mock_provider
        
        mock_connector = Mock()
        mock_connector.list_folders.return_value = ["folder1/", "folder2/"]
        mock_connector_class.return_value = mock_connector
        
        client = TestClient(app)
        response = client.post(
            "/api/v1/ingestion/list-prefixes",
            json={
                "storage_provider": "aws",
                "storage_credentials": {
                    "access_key": "key",
                    "secret_key": "secret",
                    "bucket": "bucket",
                },
                "prefix": "test/",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "folder1/" in data["prefixes"]
        assert "folder2/" in data["prefixes"]
    
    @patch("src.modules.ingestion.routers.ingestion_fastapi.AUTH_TOKEN", "test-token")
    def test_list_prefixes_missing_credentials(self, _):
        """Test prefix listing without credentials."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/ingestion/list-prefixes",
            json={
                "storage_provider": "aws",
                "storage_credentials": {},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Storage credentials required" in data["detail"]["message"]

