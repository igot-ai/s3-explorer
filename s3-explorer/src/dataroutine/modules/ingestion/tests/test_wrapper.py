import pytest
from unittest.mock import MagicMock
from dataroutine.modules.ingestion.wrapper import IngestionWrapper, init_ingestion_wrapper, get_ingestion_wrapper, reset_ingestion_wrapper

class TestIngestionWrapper:
    def setup_method(self):
        reset_ingestion_wrapper()

    def teardown_method(self):
        reset_ingestion_wrapper()

    def test_init_and_get_wrapper(self):
        mock_client = MagicMock()
        init_ingestion_wrapper(mock_client)
        wrapper = get_ingestion_wrapper()
        assert wrapper is not None
        assert wrapper._get_client() == mock_client

    def test_get_wrapper_uninitialized_raises_error(self):
        with pytest.raises(RuntimeError, match="Ingestion wrapper not initialized"):
            get_ingestion_wrapper()

    def test_trigger_ingestion_success(self):
        # Arrange
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.task_id = "test-task-id"
        mock_response.status = "started"
        mock_response.success = True
        mock_response.error = None
        mock_client.return_value = mock_response
        
        init_ingestion_wrapper(mock_client)
        wrapper = get_ingestion_wrapper()
        
        # Act
        result = wrapper.trigger_ingestion(
            source_path="test/path",
            workspace_id="ws-1",
            project_id="proj-1",
            catalogs=[{"id": "cat-1", "instruction": "instr"}]
        )
        
        # Assert
        assert result.task_id == "test-task-id"
        assert result.success is True
        assert result.status == "started"
        assert result.error is None
        
        mock_client.assert_called_once()

    def test_trigger_ingestion_failure(self):
        # Arrange
        mock_client = MagicMock()
        mock_client.side_effect = Exception("RPC Error")
        
        init_ingestion_wrapper(mock_client)
        wrapper = get_ingestion_wrapper()
        
        # Act
        result = wrapper.trigger_ingestion(
            source_path="test/path",
            workspace_id="ws-1",
            project_id="proj-1",
            catalogs=[]
        )
        
        # Assert
        assert result.success is False
        assert result.status == "failed"
        assert "RPC Error" in result.error
