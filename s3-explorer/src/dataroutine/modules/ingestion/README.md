# Ingestion Module

The **Ingestion Module** is a self-contained, high-performance data processing engine designed to acquire, process, classify, and upload documents from various storage providers into the Datalog knowledge base.

It operates as an independent service within the application, orchestrated by a robust pipeline that handles file retrieval, text extraction, AI-based classification, and metadata enrichment.

---

## 🌊 Ingestion Flow

The ingestion process is managed by the `IngestionPipeline` and executes in two main phases to ensure efficiency and data integrity.

### 🔄 Phase 1: Processing & Classification
1.  **Discovery**: The pipeline scans the source (e.g., S3 bucket) for files and folders.
2.  **Download**: Files are downloaded to a secure temporary workspace.
3.  **Preprocessing**:
    *   **Conversion**: Documents like DOCX are converted to PDF/Markdown.
    *   **Extraction**: Archives (ZIP, TAR) are extracted to process contained files.
4.  **Reading**: Text is extracted using specialized readers (`MarkItDown`, `PyMuPDF`, `PDFPlumber`).
5.  **Classification**: The `LLMClassifier` analyzes the content to determine the document type and assigns it to the correct **Catalog** (Schema).

### 🚀 Phase 2: Upload & Enrichment
1.  **Sorting**: Files are prioritized based on dependency (e.g., "fetch all metadata" catalogs are processed last).
2.  **Aggregation**: Folder-level metadata is aggregated to provide context for files.
3.  **Upload**: Files are uploaded to the Datalog API (`DataCollectionAPIHandler`).
4.  **Enrichment**:
    *   Assets trigger server-side transformation jobs.
    *   The pipeline polls for status updates.
    *   Extracted metadata is returned and associated with the file context.

---

## 🏗️ Core Components

### 1. Connectors (`core/connectors`)
Handles interaction with external storage providers.
*   **SourceConnector**: Abstract base class for data sources.
*   **S3SourceConnector**: Implementation for AWS S3 and compatible providers (MinIO, Wasabi, R2).

### 2. Processors (`core/processors`)
Transforms files before text extraction.
*   **FileProcessorChain**: Manages a sequence of processors.
*   **DocxToPdfConverter**: Converts Word documents using LibreOffice.
*   **ArchiveExtractor**: Handles ZIP/TAR archives using `patool` or standard libraries.

### 3. Readers (`core/readers`)
Responsible for extracting raw text from documents.
*   **MarkitdownReader**: (Default) Uses Microsoft's MarkItDown for versatile extraction.
*   **PyMuPDFReader**: High-performance PDF text extraction.
*   **PDFPlumberReader**: Precise layout-based PDF extraction.

### 4. Classifiers (`core/classifiers`)
AI logic for sorting documents.
*   **LLMClassifier**: Uses Large Language Models (via DSPy) to categorize documents based on content and predefined catalogs.

### 5. Handlers (`core/handlers`)
Manages the destination of processed data.
*   **DataCollectionAPIHandler**: Uploads assets to the Datalog API, handles authentication, and polls for transformation results.

---

## 📡 API Usage

The ingestion module exposes a REST API for triggering jobs.

### POST `/api/v1/ingestion/run`

Triggers a new ingestion job.

**Request Body:**
```json
{
  "config": {
    "source_path": "documents/legal_contracts/",
    "storage_provider": "aws",
    "storage_credentials": {
      "access_key": "...",
      "secret_key": "...",
      "bucket": "my-corporate-bucket",
      "region": "us-east-1"
    },
    "workspace_id": "ws_123456",
    "project_id": "proj_987654",
    "recursive": true
  },
  "catalogs": [
    {
      "id": "contracts",
      "instruction": "Legal agreements and contracts",
      "fetch_all_metadata": false
    },
    {
      "id": "invoices",
      "instruction": "Billing statements and invoices",
      "fetch_all_metadata": true
    }
  ]
}
```

---

## 📂 Directory Structure

```plaintext
ingestion/
├── config/             # Configuration and settings
├── core/
│   ├── classifiers/    # AI Classification logic
│   ├── connectors/     # Storage providers (S3, etc.)
│   ├── handlers/       # API interaction handlers
│   ├── processors/     # File conversion & extraction
│   ├── readers/        # Text extraction strategies
│   ├── models.py       # Data models (FileContext, Catalog)
│   └── pipeline.py     # Main orchestration logic
├── routers/            # FastAPI endpoints
├── schemas/            # Request/Response validation
└── services/           # External service integrations (Datalog)
```
