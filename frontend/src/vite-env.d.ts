/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CATALOG_API_URL: string;
  readonly VITE_INGESTION_API_URL: string;
  readonly VITE_AUTH_TOKEN: string;
  readonly VITE_WORKSPACE_ID: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
