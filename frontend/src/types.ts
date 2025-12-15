// ============ Core Types ============

export type RoutineStatus = 'draft' | 'active';

export interface Routine {
  id: string;
  name: string;
  projectId: string;
  projectName: string;
  status: RoutineStatus;
  createdAt: string;
  updatedAt: string;
  nodes: Node[];
  connections: Connection[];
}

// ============ Node Types ============

export type NodeType = 's3-connector' | 'collection';

export interface NodePosition {
  x: number;
  y: number;
}

export interface Node {
  id: string;
  type: NodeType;
  position: NodePosition;
  data: NodeData;
}

export type NodeData = S3ConnectorData | CollectionData;

// Storage provider types compatible with s3-explorer
export type StorageProviderType = 'aws' | 'backblaze' | 'wasabi' | 'gcs' | 'digitalocean' | 'cloudflare' | 'hetzner';

// Provider-specific region options
export const AWS_REGIONS = [
  'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
  'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-north-1',
  'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-northeast-2', 'ap-south-1',
  'sa-east-1', 'ca-central-1'
] as const;

export const WASABI_REGIONS = [
  'us-east-1', 'us-east-2', 'us-central-1', 'us-west-1',
  'eu-central-1', 'eu-central-2', 'eu-west-1', 'eu-west-2',
  'ap-northeast-1', 'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2'
] as const;

export const DIGITALOCEAN_REGIONS = ['nyc3', 'ams3', 'sgp1', 'fra1', 'sfo3'] as const;

export const HETZNER_REGIONS = ['nbg1', 'fsn1', 'hel1', 'ash', 'hil', 'sin'] as const;

export interface S3ConnectorData {
  type: 's3-connector';
  name: string;
  providerType: StorageProviderType;
  prefix: string;
  syncMode: 'incremental' | 'full' | 'manual';
  
  // AWS S3 / Wasabi / DigitalOcean / Hetzner common fields
  accessKey?: string;
  secretKey?: string;
  bucket?: string;
  region?: string;
  
  // Cloudflare R2 specific
  accountId?: string;
  
  // Backblaze B2 specific
  applicationKeyId?: string;
  applicationKey?: string;
  bucketName?: string;
  
  // Google Cloud Storage specific
  projectId?: string;
  credentialsJson?: string;
}

export interface CollectionData {
  type: 'collection';
  name: string;
  collectionName: string;
  metadataSourceCollectionId?: string; // ID of another collection node for context
  // Ingestion API fields (maps to Catalog in backend)
  catalogId?: string; // Unique ID for this catalog
  instruction?: string; // Classification instruction for LLM
  fetchAllMetadata?: boolean; // If true, aggregate metadata from all catalogs
}

// ============ Connection Types ============

export interface Connection {
  id: string;
  from: string;
  to: string;
}

// ============ Project Types (from Datalog) ============

export interface Project {
  id: string;
  name: string;
  description?: string;
}

// ============ Stats Types (for Active Routine View) ============

export interface RoutineStats {
  processed: number;
  pending: number;
  errors: number;
  successRate: number;
}

export interface ProcessedFile {
  id: string;
  fileName: string;
  targetCollection: string;
  processedAt: string;
  status: 'success' | 'error';
}

// ============ Ingestion API Types ============

export interface IngestionStorageCredentials {
  access_key?: string;
  secret_key?: string;
  bucket?: string;
  region?: string;
  account_id?: string;
  project_id?: string;
  bucket_name?: string;
  credentials_json?: string;
  application_key_id?: string;
  application_key?: string;
}

export interface IngestionConfig {
  source_path: string;
  recursive?: boolean;
  pages_to_read?: number;
  storage_provider: StorageProviderType;
  storage_credentials: IngestionStorageCredentials;
  workspace_id: string;
  project_id: string;
  auth_token: string;
  reader_type?: string;
  api_base_url?: string;
}

export interface IngestionCatalog {
  id: string;
  instruction: string;
  fetch_all_metadata: boolean;
}

export interface IngestionRequest {
  config: IngestionConfig;
  catalogs: IngestionCatalog[];
}

export interface IngestionFileResult {
  source_path: string;
  status: string;
  classified_catalog_id: string | null;
  error_message: string | null;
  metadata: Record<string, unknown>;
}

export interface IngestionFolderResult {
  folder_path: string;
  successful_count: number;
  failed_count: number;
  files: IngestionFileResult[];
}

export interface IngestionResponse {
  success: boolean;
  message: string;
  total_folders: number;
  total_files: number;
  successful: number;
  failed: number;
  success_rate: string;
  execution_time: string;
  folders: IngestionFolderResult[];
  errors?: string[];
}

// Execution state for UI
export type ExecutionStatus = 'idle' | 'running' | 'completed' | 'failed';

export interface ExecutionState {
  status: ExecutionStatus;
  startTime?: string;
  endTime?: string;
  response?: IngestionResponse;
  error?: string;
}

