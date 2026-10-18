/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL (no trailing slash). Default http://localhost:8000. */
  readonly VITE_API_URL?: string;
  /** Public credentials of the read-only demo. If missing, the login doesn't offer the demo. */
  readonly VITE_DEMO_EMAIL?: string;
  readonly VITE_DEMO_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
