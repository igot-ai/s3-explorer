/**
 * API Layer - Integrated with backend APIs
 *
 * Configuration loaded from environment variables (.env file)
 */

import type {
  Routine,
  Project,
  IngestionRequest,
  IngestionResponse,
  S3ConnectorData,
  CollectionData,
} from '../types';

// API URLs from environment
const CATALOG_API_URL = import.meta.env.VITE_CATALOG_API_URL;
const INGESTION_API_URL = import.meta.env.VITE_INGESTION_API_URL;

// Auth configuration from environment
const AUTH_TOKEN = import.meta.env.VITE_AUTH_TOKEN;
const WORKSPACE_ID = import.meta.env.VITE_WORKSPACE_ID;

// Helper to make authenticated requests
async function catalogFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${CATALOG_API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${AUTH_TOKEN}`,
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.message || `API error: ${response.status}`);
  }

  return response.json();
}

// ============ Catalog API Types ============

interface CatalogProject {
  id: string;
  owner_id: string;
  workspace_id: string;
  name: string;
  description?: string;
  is_prod: boolean;
  created_at: string;
  updated_at: string;
  collections_count: number;
  datasets_count: number;
  assets_count: number;
}

interface CatalogCollection {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  table_type: string;
  status: string;
}

// ============ Project API ============

/**
 * Fetch all projects from Catalog API
 */
export async function fetchProjects(): Promise<Project[]> {
  try {
    const params = new URLSearchParams({
      workspace_id: WORKSPACE_ID,
      limit: '1000',
      page: '1',
      q: '',
      sort_by: 'name asc',
    });

    const data = await catalogFetch<CatalogProject[]>(
      `/projects?${params.toString()}`
    );

    return data.map((p) => ({
      id: p.id,
      name: p.name,
      description: p.description,
    }));
  } catch (error) {
    console.error('Failed to fetch projects:', error);
    throw error;
  }
}

/**
 * Fetch collections (tables) for a project
 */
export async function fetchCollections(projectId: string): Promise<CatalogCollection[]> {
  try {
    const data = await catalogFetch<CatalogCollection[]>(
      `/projects/${projectId}/tables?limit=200`
    );

    return data;
  } catch (error) {
    console.error('Failed to fetch collections:', error);
    throw error;
  }
}

/**
 * Fetch columns for a table (catalog)
 */
export async function fetchColumns(catalogId: string): Promise<any[]> {
  try {
    const data = await catalogFetch<any[]>(
      `/tables/${catalogId}/columns?limit=200`
    );
    return data;
  } catch (error) {
    console.error('Failed to fetch columns:', error);
    throw error;
  }
}

// ============ Routine API (local storage managed via Zustand) ============

/**
 * Fetch all routines - stored locally via Zustand
 */
export async function fetchRoutines(): Promise<Routine[]> {
  return []; // Managed by Zustand localStorage
}

/**
 * Create a new routine
 */
export async function createRoutine(routine: Routine): Promise<Routine> {
  return routine; // Managed by Zustand
}

/**
 * Update a routine
 */
export async function updateRoutine(id: string, updates: Partial<Routine>): Promise<Routine> {
  return { id, ...updates } as Routine; // Managed by Zustand
}

/**
 * Delete a routine
 */
export async function deleteRoutine(id: string): Promise<void> {
  console.log('Deleted routine:', id); // Managed by Zustand
}

/**
 * Activate a routine
 */
export async function activateRoutine(id: string): Promise<Routine> {
  return { id, status: 'active' } as Routine; // Managed by Zustand
}

// ============ Ingestion Pipeline API ============

/**
 * Build ingestion request from routine configuration
 */
export function buildIngestionRequest(routine: Routine): IngestionRequest {
  // Find S3 connector node
  const s3Node = routine.nodes.find((n) => n.type === 's3-connector');
  if (!s3Node) {
    throw new Error('No S3 Connector found in routine');
  }

  const s3Data = s3Node.data as S3ConnectorData;

  // Build storage credentials based on provider type
  const storageCredentials: IngestionRequest['config']['storage_credentials'] = {};

  switch (s3Data.providerType) {
    case 'aws':
    case 'wasabi':
    case 'digitalocean':
    case 'hetzner':
      storageCredentials.access_key = s3Data.accessKey;
      storageCredentials.secret_key = s3Data.secretKey;
      storageCredentials.bucket = s3Data.bucket;
      storageCredentials.region = s3Data.region;
      break;
    case 'cloudflare':
      storageCredentials.access_key = s3Data.accessKey;
      storageCredentials.secret_key = s3Data.secretKey;
      storageCredentials.bucket = s3Data.bucket;
      storageCredentials.account_id = s3Data.accountId;
      storageCredentials.region = 'us-east-1'; // R2 uses us-east-1
      break;
    case 'backblaze':
      storageCredentials.application_key_id = s3Data.applicationKeyId;
      storageCredentials.application_key = s3Data.applicationKey;
      storageCredentials.bucket_name = s3Data.bucketName;
      break;
    case 'gcs':
      storageCredentials.project_id = s3Data.projectId;
      storageCredentials.bucket_name = s3Data.bucketName;
      storageCredentials.credentials_json = s3Data.credentialsJson;
      break;
  }

  // Find collection nodes and build catalogs
  const collectionNodes = routine.nodes.filter((n) => n.type === 'collection');
  const catalogs = collectionNodes.map((node) => {
    const data = node.data as CollectionData;
    // Support legacy 'information' field for backwards compatibility with old saved routines
    const legacyInfo = (data as CollectionData & { information?: string }).information;
    return {
      id: data.catalogId || node.id, // Use catalogId if set, otherwise use node ID
      instruction: data.instruction || legacyInfo || `Documents for ${data.collectionName || data.name}`,
      fetch_all_metadata: data.fetchAllMetadata || false,
      metadata_scan: data.metadataScan,
    };
  });

  if (catalogs.length === 0) {
    throw new Error('No Collection nodes found in routine');
  }

  return {
    config: {
      source_path: s3Data.prefix || '/',  // Default to root if no prefix specified
      recursive: true,
      pages_to_read: 3,
      storage_provider: s3Data.providerType,
      storage_credentials: storageCredentials,
      workspace_id: WORKSPACE_ID,
      project_id: routine.projectId,
      auth_token: AUTH_TOKEN,
      api_base_url: CATALOG_API_URL, // Ensure backend knows the catalog API URL
    },
    catalogs,
  };
}

/**
 * Run the ingestion pipeline
 */
export async function runIngestionPipeline(request: IngestionRequest): Promise<IngestionResponse> {
  const response = await fetch(`${INGESTION_API_URL}/run`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${AUTH_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.message || data.errors?.join(', ') || 'Pipeline execution failed');
  }

  return data as IngestionResponse;
}

/**
 * Check ingestion API health
 */
export async function checkIngestionHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${INGESTION_API_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * List S3 prefixes/folders for a given storage configuration
 */
export async function listS3Prefixes(
  s3Data: S3ConnectorData,
  prefix: string = ''
): Promise<string[]> {
  // Build storage credentials based on provider type
  const storageCredentials: Record<string, string> = {};

  switch (s3Data.providerType) {
    case 'aws':
    case 'wasabi':
    case 'digitalocean':
    case 'hetzner':
      if (s3Data.accessKey) storageCredentials.access_key = s3Data.accessKey;
      if (s3Data.secretKey) storageCredentials.secret_key = s3Data.secretKey;
      if (s3Data.bucket) storageCredentials.bucket = s3Data.bucket;
      if (s3Data.region) storageCredentials.region = s3Data.region;
      break;
    case 'cloudflare':
      if (s3Data.accessKey) storageCredentials.access_key = s3Data.accessKey;
      if (s3Data.secretKey) storageCredentials.secret_key = s3Data.secretKey;
      if (s3Data.bucket) storageCredentials.bucket = s3Data.bucket;
      if (s3Data.accountId) storageCredentials.account_id = s3Data.accountId;
      break;
    case 'backblaze':
      if (s3Data.applicationKeyId) storageCredentials.application_key_id = s3Data.applicationKeyId;
      if (s3Data.applicationKey) storageCredentials.application_key = s3Data.applicationKey;
      if (s3Data.bucketName) storageCredentials.bucket_name = s3Data.bucketName;
      break;
    case 'gcs':
      if (s3Data.projectId) storageCredentials.project_id = s3Data.projectId;
      if (s3Data.bucketName) storageCredentials.bucket_name = s3Data.bucketName;
      if (s3Data.credentialsJson) storageCredentials.credentials_json = s3Data.credentialsJson;
      break;
  }

  const response = await fetch(`${INGESTION_API_URL}/list-prefixes`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${AUTH_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      storage_provider: s3Data.providerType,
      storage_credentials: storageCredentials,
      prefix: prefix,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.message || data.errors?.join(', ') || 'Failed to list prefixes');
  }

  return data.prefixes || [];
}

// Export constants for use elsewhere
export { AUTH_TOKEN, WORKSPACE_ID, CATALOG_API_URL, INGESTION_API_URL };
