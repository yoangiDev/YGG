/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base de la API (sin barra final). Por defecto http://localhost:8000. */
  readonly VITE_API_URL?: string;
  /** Credenciales públicas de la demo de solo lectura. Si faltan, el login no ofrece la demo. */
  readonly VITE_DEMO_EMAIL?: string;
  readonly VITE_DEMO_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
