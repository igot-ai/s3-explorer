# Ingestion Wrapper Integration Guide

## Overview

The ingestion wrapper provides a clean interface for triggering ingestion pipeline jobs via gRPC, abstracting the gRPC client details from route handlers and other services.

## Architecture

The wrapper follows a dependency injection pattern to avoid circular dependencies:

```
┌─────────────────────────────────────────────────────────────┐
│ App Bootstrap (bootstrap.py)                                 │
│                                                               │
│  1. Import igotapi.client.run_ingestion_pipeline             │
│  2. Call init_ingestion_wrapper(run_ingestion_pipeline)      │
│  3. Wrapper is now ready for use                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Dataroutine Wrapper (wrapper.py)                             │
│                                                               │
│  - Singleton instance holds injected gRPC client             │
│  - Routes call get_ingestion_wrapper()                       │
│  - Wrapper delegates to injected client                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Catalog Wrapper (catalog/ingestion_wrapper.py)               │
│                                                               │
│  - Lazy-loads dataroutine wrapper when needed                │
│  - Transforms single catalog to catalogs list                │
│  - Provides catalog-specific interface                       │
└─────────────────────────────────────────────────────────────┘
```

## Initialization

### 1. Bootstrap Initialization (Required)

The wrapper **MUST** be initialized during app startup in `bootstrap.py`:

```python
# In core-services/flowgpt/bootstrap.py
from igotapi.client import run_ingestion_pipeline
from dataroutine.modules.ingestion.wrapper import init_ingestion_wrapper

# During app startup (in gen_init)
init_ingestion_wrapper(run_ingestion_pipeline)
logger.info("Ingestion wrapper initialized with gRPC client")
```

### 2. Using the Wrapper in Routes

Routes can then access the wrapper via the singleton getter:

```python
# In route handlers
from dataroutine.modules.ingestion.wrapper import get_ingestion_wrapper

wrapper = get_ingestion_wrapper()
result = wrapper.trigger_ingestion(
    source_path="raw-documents/",
    workspace_id="ws-123",
    project_id="proj-456",
    auth_token="token-789",
    catalogs=[{"id": "cat-1", "instruction": "Legal docs", "fetch_all_metadata": False}],
)
```

### 3. Using via Catalog Wrapper

The catalog service uses a dedicated wrapper that delegates to the dataroutine wrapper:

```python
# In catalog service
from igotapi.catalog.core.ingestion_wrapper import get_catalog_ingestion_wrapper

wrapper = get_catalog_ingestion_wrapper()
task_id = wrapper.trigger_task(
    source_path="raw-documents/",
    workspace_id="ws-123",
    project_id="proj-456",
    auth_token="token-789",
    catalog_config={"id": "cat-1", "instruction": "Legal docs", "fetch_all_metadata": False},
)
```

## Key Design Decisions

### 1. Dependency Injection over Auto-Import

❌ **Old Approach (Circular Dependency):**
```python
# In wrapper.py - BAD
def get_ingestion_wrapper():
    if _wrapper_instance is None:
        from igotapi.client import run_ingestion_pipeline  # Circular import!
        _wrapper_instance = IngestionWrapper(run_ingestion_pipeline)
    return _wrapper_instance
```

✅ **New Approach (Dependency Injection):**
```python
# In bootstrap.py - GOOD
from igotapi.client import run_ingestion_pipeline
from dataroutine.modules.ingestion.wrapper import init_ingestion_wrapper

init_ingestion_wrapper(run_ingestion_pipeline)  # Inject dependency
```

### 2. Initialization Validation

The wrapper validates that it has been properly initialized before use:

```python
def get_ingestion_wrapper() -> IngestionWrapper:
    if _wrapper_instance is None:
        raise RuntimeError(
            "Ingestion wrapper not initialized. "
            "Call init_ingestion_wrapper() during app bootstrap."
        )
    return _wrapper_instance
```

This ensures that:
- Routes cannot use the wrapper before initialization
- Clear error messages guide developers to proper setup
- No silent failures or missing client scenarios

### 3. Single Responsibility

Each wrapper layer has a clear responsibility:

- **dataroutine/wrapper.py**: Core wrapper that delegates to gRPC client
- **catalog/ingestion_wrapper.py**: Catalog-specific interface and transformations
- **bootstrap.py**: Initialization and dependency injection

## Testing

For testing, use the `reset_ingestion_wrapper()` function to reset the singleton:

```python
# In tests
from dataroutine.modules.ingestion.wrapper import (
    init_ingestion_wrapper,
    reset_ingestion_wrapper,
)

def test_ingestion():
    # Setup
    mock_client = Mock(spec=IngestionClientProtocol)
    init_ingestion_wrapper(mock_client)
    
    # Test...
    
    # Teardown
    reset_ingestion_wrapper()
```

## Error Handling

The wrapper provides clear error messages for common issues:

| Error | Cause | Solution |
|-------|-------|----------|
| `RuntimeError: Ingestion wrapper not initialized` | `get_ingestion_wrapper()` called before `init_ingestion_wrapper()` | Call `init_ingestion_wrapper()` in bootstrap |
| `RuntimeError: Ingestion client not configured` | Wrapper initialized with `None` client | Pass valid client to `init_ingestion_wrapper()` |

## Migration from Old Code

If you have code using the old auto-import pattern:

1. **Remove any manual client imports** in wrapper.py
2. **Add initialization** to bootstrap.py as shown above
3. **Routes remain unchanged** - they still use `get_ingestion_wrapper()`
4. **Test thoroughly** to ensure wrapper is initialized before first use

## Benefits

1. **No Circular Dependencies**: igotapi and dataroutine are properly decoupled
2. **Explicit Initialization**: Clear startup sequence with validation
3. **Testability**: Easy to inject mock clients for testing
4. **Clear Error Messages**: Developers get helpful guidance when setup is incorrect
5. **Single Source of Truth**: All initialization happens in bootstrap.py








