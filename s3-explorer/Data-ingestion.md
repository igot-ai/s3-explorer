Data Ingestion Pipeline - C4 Architecture Design
---

C4 Level 1: System Context
                    +------------------+
                    |   Admin User     |
                    | (Configure       |
                    |  Collections,    |
                    |  Trigger Jobs)   |
                    +--------+---------+
                             |
                             v
+----------------+    +------+--------+    +------------------+
|   Source S3    |<-->|    Data       |<-->|   LLM Service    |
|   Storage      |    |   Ingestion   |    | (Classification) |
| (Raw Files)    |    |   Pipeline    |    +------------------+
+----------------+    +------+--------+
                             |
                             v
                    +--------+---------+
                    |  Target S3       |
                    |  Collections     |
                    | (Organized by    |
                    |  Catalog ID)     |
                    +------------------+
Actors:

Admin User: Defines catalogs, configures S3 paths, triggers ingestion jobs
Source S3: Contains unorganized raw files (PDF, DOCX, ZIP, RAR)
LLM Service: Classifies documents based on content (pluggable: OpenAI, Anthropic, Azure, Local)
Target S3: Same bucket with organized folder structure per collection
---

C4 Level 2: Container Diagram
+------------------------------------------------------------------------+
|                        Data Ingestion System                           |
+------------------------------------------------------------------------+
|                                                                        |
|  +------------------+     +-------------------+     +-----------------+ |
|  |   Pipeline       |     |   File            |     |  Classification | |
|  |   Orchestrator   |---->|   Processor       |---->|  Engine         | |
|  |                  |     |                   |     |                 | |
|  | - Job scheduling |     | - DOCX->PDF       |     | - LLM routing   | |
|  | - Folder walking |     | - Archive extract |     | - PDF reading   | |
|  | - State tracking |     | - File validation |     | - Metadata scan | |
|  +--------+---------+     +-------------------+     +--------+--------+ |
|           |                                                  |          |
|           v                                                  v          |
|  +------------------+     +-------------------+     +-----------------+ |
|  |   Storage        |     |   Catalog         |     |  Collection     | |
|  |   Adapter        |     |   Registry        |     |  Handler        | |
|  |                  |     |                   |     |                 | |
|  | - S3 operations  |     | - Catalog CRUD    |     | - Upload files  | |
|  | - File streaming |     | - Metadata schema |     | - Attach meta   | |
|  +------------------+     +-------------------+     +-----------------+ |
|                                                                        |
+------------------------------------------------------------------------+
---

Component Interaction Flow
[S3 Source Path]
       |
       v
+------------------+
| SourceConnector  |  --> Lists all folders/files recursively
+--------+---------+
         |
         v
+------------------+
| FolderTracker    |  --> Creates FolderContext for each top-level folder
+--------+---------+
         |
    +----+----+
    |         |
    v         v
+-------+  +----------+
| .docx |  | .zip/.rar|
+---+---+  +----+-----+
    |           |
    v           v
+----------------+  +------------------+
| FileConverter  |  | ArchiveExtractor |
| (DOCX->PDF)    |  | (patool)         |
+-------+--------+  +---------+--------+
        |                     |
        +----------+----------+
                   |
                   v
          +--------+--------+
          | DocumentReader  |  --> Extract first 3 pages text
          +--------+--------+
                   |
                   v
          +--------+--------+
          |   Classifier    |  --> LLM classifies to catalog.id
          +--------+--------+
          +--------+---------+
          | CollectionHandler|  --> Upload to an APIProvider to manage collection
          +------------------+
---
