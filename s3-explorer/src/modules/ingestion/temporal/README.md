# Temporal Workflow Integration for Ingestion Pipeline

This module provides Temporal workflow orchestration for the data ingestion pipeline, enabling distributed execution and integration with other services like catalog without tight coupling.

## Architecture

The Temporal wrapper follows a clean separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│ External Services (e.g., catalog)                           │
│  - Use gRPC endpoint or client helper                       │
│  - No direct dependency on pipeline implementation           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ gRPC Service (agent/igent/service.py)                       │
│  - RunIngestionPipeline endpoint                            │
│  - Converts proto → IngestionJobParams                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Temporal Workflow (IngestionPipelineWorkflow)               │
│  - Orchestrates pipeline execution                          │
│  - Handles retries and timeouts                             │
│  - Optional callback workflow support                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Temporal Activity (run_ingestion_pipeline_activity)          │
│  - Executes actual pipeline                                 │
│  - Non-deterministic operations (I/O, API calls)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ IngestionPipeline (core/pipeline.py)                        │
│  - Actual pipeline implementation                           │
│  - No Temporal dependencies                                │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### Models (`temporal/models.py`)

- **IngestionJobParams**: Single dataclass for workflow input (follows Temporal best practices)
- **IngestionResult**: Workflow output with execution statistics
- **CatalogParams**: Catalog configuration for document classification

### Activities (`temporal/activities.py`)

- **run_ingestion_pipeline_activity**: Main activity that executes the pipeline
- **notify_ingestion_complete_activity**: Optional callback notification

### Workflows (`temporal/workflows.py`)

- **IngestionPipelineWorkflow**: Main workflow for single ingestion jobs
- **IngestionStatusWorkflow**: Parent workflow for coordinating multiple jobs

## Usage

### From External Services (e.g., catalog)

```python
from igotapi.client import run_ingestion_pipeline

response = run_ingestion_pipeline(
    source_path="raw-documents/legal/",
    workspace_id="ws-123",
    project_id="proj-456",
    auth_token="token-789",
    catalogs=[
        {
            "id": "legal-contracts",
            "instruction": "Legal domain documents",
            "fetch_all_metadata": False,
        }
    ],
    storage_credentials={
        "access_key": "...",
        "secret_key": "...",
        "bucket": "my-bucket",
        "region": "us-east-1",
    },
    task_id="custom-task-id",  # Optional
    callback_workflow="ProcessCatalogResults",  # Optional
    callback_params={"project_id": "proj-456"},  # Optional
)

print(f"Task ID: {response.task_id}, Status: {response.status}")
```

### Direct Temporal Client Usage

```python
from temporalio.client import Client
from dataroutine.modules.ingestion.temporal.models import IngestionJobParams

client = await get_temporal_client()

params = IngestionJobParams(
    source_path="raw-documents/",
    workspace_id="ws-123",
    project_id="proj-456",
    auth_token="token-789",
    catalogs=[{"id": "cat1", "instruction": "Test"}],
    storage_credentials={"access_key": "...", "secret_key": "...", "bucket": "..."},
)

handle = await client.start_workflow(
    "IngestionPipelineWorkflow",
    params,
    id=f"ingestion-{params.task_id}",
    task_queue="ingestion-pipeline-task-queue",
)
```

## Worker Registration

The ingestion worker is registered in `consumer.py`:

```bash
python consumer.py ingestion
```

This starts a worker that processes:
- `IngestionPipelineWorkflow` - Single job execution
- `IngestionStatusWorkflow` - Multiple job coordination

## Task Queue

The default task queue is defined in:
- `dataroutine.modules.ingestion.temporal.workflows.INGESTION_TASK_QUEUE`
- Also available as `igotapi.const.INGESTION_PIPELINE_TASK_QUEUE`

## Decoupling Design

The wrapper ensures loose coupling:

1. **External services** use `IngestionJobParams` (simple dataclass) - no pipeline dependencies
2. **Pipeline implementation** has no Temporal dependencies - can run standalone
3. **Temporal wrapper** bridges the gap - converts params to pipeline config

## Extensibility

The wrapper can be extended outside dataroutine:

1. **Custom workflows**: Import `IngestionPipelineWorkflow` and compose with other workflows
2. **Custom activities**: Add new activities that use `IngestionJobParams`
3. **Callback workflows**: Use `callback_workflow` and `callback_params` to chain workflows

## Testing

Unit tests are provided in:
- `tests/test_temporal_models.py` - Model serialization/deserialization
- `tests/test_temporal_activities.py` - Activity logic (mocked pipeline)

Run tests:
```bash
pytest api/dataroutine/s3-explorer/src/modules/ingestion/tests/test_temporal_*.py
```

## Integration with Catalog

The catalog service can delegate to ingestion pipeline:

```python
# In catalog service
from igotapi.client import run_ingestion_pipeline

# Trigger ingestion when catalog is ready
response = run_ingestion_pipeline(
    source_path=f"s3://bucket/{catalog.source_path}",
    workspace_id=catalog.workspace_id,
    project_id=catalog.project_id,
    auth_token=user_token,
    catalogs=[{
        "id": catalog.id,
        "instruction": catalog.classification_instruction,
        "fetch_all_metadata": catalog.fetch_all_metadata,
    }],
    callback_workflow="ProcessCatalogIngestionResults",
    callback_params={"catalog_id": catalog.id},
)
```

No tight coupling - catalog only needs to know about `run_ingestion_pipeline` function and its parameters.

