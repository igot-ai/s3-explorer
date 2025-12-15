## Updated Design - Simplified Architecture

The ingestion module now has a clean, self-contained design:

```
ingestion/
├── connectors/
│   ├── storage.py        # All storage providers (AWS, GCS, DO, etc.)
│   ├── s3_utils.py       # S3 utility functions
│   ├── s3_connector.py   # S3 source connector
│   └── base.py           # SourceConnector interface
```

### Benefits of This Design

1. **Self-Contained**: All storage logic is within the ingestion module
2. **No Parent Dependencies**: Doesn't rely on imports from parent directory
3. **Clear Separation**: Storage providers are in connectors where they belong
4. **Easier Testing**: All components can be tested independently
5. **Simplified Imports**: `from ingestion.connectors import get_storage_provider`

### Import Pattern

```python
# Simple, clean imports
from ingestion.connectors import get_storage_provider, S3SourceConnector
from ingestion.classifiers import LLMClassifier
from ingestion.handlers import S3CollectionHandler

# Create components
provider = get_storage_provider("aws", **credentials)
source = S3SourceConnector(provider)
handler = S3CollectionHandler(provider)
classifier = LLMClassifier(provider="openai", api_key="...")
```

