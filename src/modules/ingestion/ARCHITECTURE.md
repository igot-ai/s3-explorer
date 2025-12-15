# Data Ingestion Pipeline - Architecture Documentation

## Overview

A production-ready, self-contained data ingestion framework for processing documents from S3, classifying them with LLM, and routing to collections.

## Design Philosophy

### SOLID Principles
- **Single Responsibility**: Each class has one clear purpose
- **Open/Closed**: Extensible through interfaces, closed for modification
- **Liskov Substitution**: All implementations are interchangeable
- **Interface Segregation**: Focused, minimal interfaces
- **Dependency Inversion**: Depends on abstractions, not concrete implementations

### Key Patterns
- **Strategy**: Swap implementations (LLM, readers, storage) without changing pipeline
- **Chain of Responsibility**: Route files to appropriate processors
- **Template Method**: Customizable prompts with shared structure
- **Factory**: Centralized component creation
- **Observer**: Progress tracking via callbacks
- **Repository**: Centralized catalog management

## Architecture Layers

### 1. Core Layer (`ingestion/core/`)

#### Data Models (`models.py`)
```python
FileStatus(Enum)          # File processing lifecycle states
Catalog                   # Document collection definition
FileContext               # Single file processing context
FolderContext             # Folder-level processing context
IngestionJobConfig        # Job configuration
ClassificationResult      # LLM classification output
PipelineResult            # Pipeline execution summary
```

**Key Responsibilities:**
- Define domain models and business rules
- Provide validation and helper methods
- Track processing state and metadata

#### Pipeline Orchestrator (`pipeline.py`)
```python
IngestionPipeline
  ├── run(config) -> PipelineResult
  ├── _process_file(file_ctx, config, folder_ctx)
  ├── _aggregate_folder_metadata(folder_ctx, catalogs)
  └── _build_result(folder_contexts, execution_time)
```

**Workflow:**
1. List all folders from source
2. For each folder:
   - Walk and download files
   - Process (convert/extract)
   - Read document text
   - Classify and extract metadata
   - Upload to collection
3. Aggregate results

#### Catalog Registry (`registry.py`)
```python
CatalogRegistry
  ├── add_catalog(catalog)
  ├── remove_catalog(catalog_id)
  ├── update_catalog(catalog)
  ├── get_by_id(catalog_id)
  ├── load_from_json(file_path)
  ├── load_from_yaml(file_path)
  ├── save_to_json(file_path)
  └── save_to_yaml(file_path)
```

### 2. Connectors Layer (`ingestion/connectors/`)

#### Storage Providers (`storage.py`)
Self-contained storage abstraction supporting:
- **AWS S3** - Amazon Simple Storage Service
- **Google Cloud Storage** - GCS buckets
- **DigitalOcean Spaces** - S3-compatible
- **Cloudflare R2** - S3-compatible, no egress fees
- **Wasabi** - S3-compatible, cost-effective
- **Backblaze B2** - Low-cost storage
- **Hetzner Storage** - European storage provider

```python
StorageProvider (ABC)
  ├── upload_file(file_obj, filename)
  ├── download_file(filename) -> BinaryIO
  ├── delete_file(filename)
  ├── list_files(prefix) -> List[dict]
  └── get_file_url(filename, expires_in) -> str

get_storage_provider(provider_type, **credentials) -> StorageProvider
```

#### S3 Utilities (`s3_utils.py`)
Helper functions for S3 operations:
- Credential validation
- Filesystem/client creation
- File operations
- Folder operations

#### S3 Source Connector (`s3_connector.py`)
```python
S3SourceConnector(SourceConnector)
  ├── list_folders(prefix) -> List[str]
  ├── walk_folder(folder_path, recursive) -> Iterator[FileContext]
  ├── download_file(file_path) -> BinaryIO
  ├── get_file_metadata(file_path) -> dict
  └── file_exists(file_path) -> bool
```

### 3. Processors Layer (`ingestion/processors/`)

#### File Processor Chain (`base.py`)
```python
FileProcessor (ABC)
  ├── can_process(file_context) -> bool
  ├── process(file_context, output_dir) -> List[FileContext]
  └── get_supported_extensions() -> List[str]

FileProcessorChain
  ├── process(file_context, output_dir) -> List[FileContext]
  ├── add_processor(processor)
  └── get_processors() -> List[FileProcessor]
```

#### Document Converter (`converter.py`)
```python
DocxToPdfConverter(FileProcessor)
  # Converts DOCX/DOC to PDF using LibreOffice
  # Supports: .docx, .doc

PypandocConverter(FileProcessor)
  # Fallback converter using pypandoc
  # Requires pandoc installation
```

#### Archive Extractor (`extractor.py`)
```python
ArchiveExtractor(FileProcessor)
  # Uses patool library
  # Supports 30+ formats: ZIP, RAR, 7z, TAR, GZIP, BZIP2, XZ, ZSTANDARD, etc.
  # Reference: https://github.com/wummel/patool

SimpleZipExtractor(FileProcessor)
  # Built-in ZIP extraction fallback
  # No external dependencies
```

### 4. Readers Layer (`ingestion/readers/`)

#### Document Readers
```python
DocumentReader (ABC)
  ├── can_read(file_path) -> bool
  ├── read_pages(file_path, max_pages) -> str
  ├── read_full_document(file_path) -> str
  ├── get_page_count(file_path) -> int
  └── get_supported_formats() -> list[str]

PyMuPDFReader(DocumentReader)
  # Fast PDF reading with image support
  # Uses PyMuPDF (fitz) library

PDFPlumberReader(DocumentReader)
  # Advanced PDF extraction with table support
  # Uses pdfplumber library
  # Additional: extract_tables(file_path, page_num)
```

### 5. Classifiers Layer (`ingestion/classifiers/`)

#### Unified LLM Classifier (`llm_classifier.py`)
```python
LLMClassifier(Classifier)
  # Single gateway for multiple LLM providers

  Supported Providers:
  ├── OpenAI (GPT-4, GPT-4-turbo, GPT-3.5-turbo)
  ├── Anthropic (Claude 3 Opus, Sonnet, Haiku)
  ├── Ollama (Local models: Llama, Mistral, Mixtral)
  └── Azure OpenAI

  Methods:
  ├── classify(text, catalogs) -> ClassificationResult
  ├── find_catalog(catalog_id, text, catalogs) -> (Catalog, metadata)
  └── _generate(prompt, temperature, max_tokens) -> str
```

**Metadata Extraction:**
Optional; current classifier focuses on catalog selection and can be extended for metadata if needed.

### 6. Handlers Layer (`ingestion/handlers/`)

#### Collection Handlers
```python
CollectionHandler (ABC)
  ├── upload(file_context, catalog, file_stream, metadata) -> str
  ├── upload_with_folder_context(...) -> str
  ├── build_destination_path(file_context, catalog) -> str
  └── prepare_metadata(file_metadata, folder_context, catalog) -> dict

S3CollectionHandler(CollectionHandler)
  # Upload to S3 collections
  # Path: collections/{catalog.id}/{filename}

APICollectionHandler(CollectionHandler)
  # Upload via REST API
  # Additional methods:
  ├── authenticate()
  ├── get_collection(catalog_id)
  ├── create_collection(catalog)
  └── update_collection_metadata(catalog_id, metadata)
```

### 7. Configuration Layer (`ingestion/config/`)

#### Settings Management (`settings.py`)
```python
IngestionConfig
  # Supports loading from:
  ├── from_json(file_path)
  ├── from_yaml(file_path)
  ├── from_env()  # Environment variables
  ├── save_json(file_path)
  └── save_yaml(file_path)
```

## Component Interaction Flow

```
┌─────────────────┐
│  User/CLI       │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ IngestionPipeline│ (Orchestrator)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    v         v
┌──────────┐ ┌──────────┐
│S3Source  │ │ Catalog  │
│Connector │ │ Registry │
└────┬─────┘ └────┬─────┘
     │            │
     v            v
┌─────────────────┐
│ FolderContext   │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ FileContext     │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    v         v
┌──────────┐ ┌────────────┐
│  DOCX    │ │ ZIP/RAR    │
│Converter │ │  Extractor │
└────┬─────┘ └─────┬──────┘
     │             │
     └──────┬──────┘
            v
    ┌──────────────┐
    │ DocumentReader│
    │ (PDF Extract)│
    └──────┬───────┘
           v
    ┌──────────────┐
    │ LLMClassifier│
    │ (OpenAI/     │
    │  Claude/     │
    │  Ollama)     │
    └──────┬───────┘
           │
      ┌────┴────┐
      │         │
      v         v
┌───────────┐ ┌─────────────┐
│ Classify  │ │   Metadata  │
│ to Catalog│ │  Extraction │
└─────┬─────┘ └──────┬──────┘
      └────────┬─────┘
               v
    ┌──────────────────┐
    │CollectionHandler │
    │ (S3 or API)      │
    └──────────────────┘
```

## Data Flow

### File Processing Lifecycle

1. **Discovery**: `SourceConnector.list_folders()` → List[str]
2. **Walking**: `SourceConnector.walk_folder()` → Iterator[FileContext]
3. **Download**: `SourceConnector.download_file()` → BinaryIO
4. **Processing**: `FileProcessorChain.process()` → List[FileContext]
   - DOCX → PDF conversion
   - Archive extraction (ZIP, RAR, etc.)
5. **Reading**: `DocumentReader.read_pages()` → str
6. **Classification**: `Classifier.classify()` → ClassificationResult
7. **Metadata**: `Classifier.extract_metadata()` → Dict
8. **Upload**: `CollectionHandler.upload()` → str (path/ID)
9. **Aggregation**: Collect folder-level metadata (if enabled)

### State Transitions

```
FileStatus:
  PENDING → PROCESSING → CONVERTED → CLASSIFIED → UPLOADED
                              ↓
                          FAILED (at any stage)
```

## Configuration Schema

### Catalog Definition
```yaml
catalogs:
  - id: "legal-contracts"              # Required: Unique identifier
    information: "Legal contracts..."  # Required: Classification instruction
    content: "Legal domain docs"       # Required: Human description
    fetch_all_metadata: false          # Optional: Aggregate metadata
    metadata_scan:                     # Optional: Fields to extract
      legal_entity: "string"
      contract_type: "string"
      effective_date: "string"
```

### Pipeline Configuration
```yaml
source_path: "raw-documents/"          # Required: S3 path to process
recursive: true                        # Optional: Recurse subfolders
pages_to_read: 3                       # Optional: Pages for classification
temp_dir: "/tmp/ingestion"            # Optional: Temp storage location

classifier_type: "openai"              # Required: openai|anthropic|ollama|azure
classifier_model: "gpt-4o-mini"       # Optional: Model name
# classifier_api_key set via env var  # Required for cloud providers

handler_type: "s3"                     # Required: s3|api
reader_type: "pymupdf"                 # Optional: pymupdf|pdfplumber

storage_provider: "aws"                # Required: aws|gcs|digitalocean|etc.
storage_credentials:                   # Required: Provider-specific
  access_key: "..."
  secret_key: "..."
  bucket: "..."
  region: "..."
```

## Extension Points

### Adding a New Storage Provider

```python
# In ingestion/connectors/storage.py
class NewStorageProvider(StorageProvider):
    def upload_file(self, file_obj, filename):
        # Implementation
        pass

    # Implement other abstract methods...

# Register in get_storage_provider()
providers['newstorage'] = NewStorageProvider
```

### Adding a New Document Reader

```python
# Create ingestion/readers/new_reader.py
from .base import DocumentReader

class NewReader(DocumentReader):
    def can_read(self, file_path):
        return file_path.suffix == '.newformat'

    def read_pages(self, file_path, max_pages):
        # Implementation
        pass

    # Implement other abstract methods...
```

### Adding a New File Processor

```python
# In ingestion/processors/custom_processor.py
from .base import FileProcessor

class CustomProcessor(FileProcessor):
    def can_process(self, file_context):
        return file_context.file_type == 'custom'

    def process(self, file_context, output_dir):
        # Process and return List[FileContext]
        pass
```

## Scalability Considerations

### Performance Optimization
- **Streaming**: Uses streaming for large files
- **Batch Operations**: Efficient S3 list operations
- **Temp File Management**: Cleans up after processing
- **Error Isolation**: Failed files don't stop the pipeline

### Future Enhancements
1. **Parallel Processing**: Add multiprocessing/threading for concurrent file processing
2. **Caching**: Cache LLM results for duplicate documents
3. **Incremental Processing**: Track processed files to avoid reprocessing
4. **Distributed Processing**: Add message queue (SQS, RabbitMQ) for distributed workers
5. **Progress Persistence**: Save/resume pipeline state

## Testing Strategy

### Unit Tests (77 tests, all passing ✅)
- **test_models.py** (22 tests): Data models validation and business logic
- **test_interfaces.py** (32 tests): Abstract interface contracts
- **test_processors.py** (15 tests): File processing components
- **test_core.py** (8 tests): Pipeline orchestration

### Test Coverage
- ✅ Data model validation
- ✅ Interface contracts
- ✅ Business logic
- ✅ Error handling
- ✅ Edge cases
- ✅ Integration points

## Deployment

### Prerequisites
```bash
# System dependencies
- Python 3.8+
- LibreOffice (for DOCX conversion)
- patool (pip install patool)

# Optional: For specific archive formats
- unrar, p7zip, etc. (see patool docs)
```

### Installation
```bash
cd ingestion
pip install -r requirements.txt
```

### Environment Variables
```bash
export INGESTION_CLASSIFIER_API_KEY="your-api-key"
export INGESTION_SOURCE_PATH="raw-documents/"
export INGESTION_CLASSIFIER_TYPE="openai"
export INGESTION_STORAGE_PROVIDER="aws"
```

### Running
```bash
# CLI
python -m ingestion.cli \
  --config config.yaml \
  --catalogs catalogs.yaml \
  --verbose

# Programmatic
from ingestion.core.pipeline import IngestionPipeline
# ... create components ...
result = pipeline.run(job_config)
```

## Monitoring & Observability

### Logging Levels
- **DEBUG**: Detailed processing information
- **INFO**: Progress updates, file status
- **WARNING**: Non-fatal issues
- **ERROR**: Processing failures

### Callbacks
```python
def on_file_processed(file_ctx: FileContext):
    print(f"{file_ctx.source_path} - {file_ctx.status}")

def on_folder_completed(folder_ctx: FolderContext):
    print(f"Folder: {folder_ctx.folder_path}")
    print(f"Success: {len(folder_ctx.get_successful_files())}")
```

### Metrics
```python
result = pipeline.run(config)
print(f"Total files: {result.total_files}")
print(f"Success rate: {result.get_success_rate():.2f}%")
print(f"Execution time: {result.execution_time_seconds:.2f}s")
```

## Security Considerations

1. **Credentials**: Never hardcode API keys or credentials
2. **Validation**: Validate all file paths to prevent directory traversal
3. **Sandboxing**: Process archives in isolated temp directories
4. **Size Limits**: Consider adding file size limits
5. **Timeout**: All external calls have timeouts

## References

- [patool Archive Manager](https://github.com/wummel/patool) - Multi-format archive extraction
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/) - PDF processing
- [pdfplumber](https://github.com/jsvine/pdfplumber) - Table extraction from PDFs
- [OpenAI API](https://platform.openai.com/docs/) - GPT models
- [Anthropic API](https://docs.anthropic.com/) - Claude models
- [Ollama](https://ollama.ai/) - Local LLM deployment

## License

Inherits license from parent S3 File Share project.
